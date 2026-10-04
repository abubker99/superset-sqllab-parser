import csv
import io
import os
import sys
import msgpack
import pyarrow as pa
import zlib
import argparse
from datetime import datetime, timezone

def parse_cache_file(file_path):
    """Reads a raw cache file, decompresses zlib, and returns a record dictionary."""
    with open(file_path, "rb") as f:
        raw_data = f.read()

    decompressed = None
    
    # Try default offset 22 (0x16) first
    try:
        decompressed = zlib.decompress(raw_data[22:])
    except zlib.error:
        # Fallback zlib scanner
        for i in range(len(raw_data) - 2):
            if raw_data[i] == 0x78 and raw_data[i:i+2] in [b'\x78\x01', b'\x78\x9c', b'\x78\xda', b'\x78\x5e']:
                try:
                    decompressed = zlib.decompress(raw_data[i:])
                    break
                except zlib.error:
                    continue
                    
    if not decompressed:
        raise ValueError("Could not find or decompress valid zlib stream.")

    payload = msgpack.unpackb(decompressed, raw=False)
    query = payload.get("query", {})
    
    query_id = payload.get("query_id") or query.get("queryId", "")
    status = payload.get("status") or query.get("state", "")
    db_name = query.get("db", "")
    user = query.get("user", "")

    sql = query.get("sql") or query.get("executedSql", "")
    sql_clean = " ".join(sql.split()) if sql else ""

    start_dttm = query.get("startDttm")
    end_dttm = query.get("endDttm")
    changed_on = query.get("changedOn") or query.get("changed_on")

    start_iso, end_iso = "", ""
    if start_dttm:
        dt = datetime.fromtimestamp(float(start_dttm) / 1000.0, tz=timezone.utc)
        start_iso = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    if end_dttm:
        dt = datetime.fromtimestamp(float(end_dttm) / 1000.0, tz=timezone.utc)
        end_iso = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    result_preview = ""
    if "data" in payload and isinstance(payload["data"], (bytes, bytearray)):
        try:
            reader = pa.ipc.open_stream(io.BytesIO(payload["data"]))
            table = reader.read_all()
            result_preview = str(table.to_pylist()[:5])
        except Exception as e:
            result_preview = f"<arrow_parse_error: {e}>"

    file_id = os.path.basename(file_path)
    return {
        "timestamp": start_iso or changed_on or "",
        "start_epoch_ms": float(start_dttm) if start_dttm else 0.0,
        "end_time": end_iso,
        "query_id": query_id,
        "user": user,
        "database": db_name,
        "status": status,
        "sql": sql_clean,
        "cache_key": file_id,
        "result_preview": result_preview,
    }

def main():
    parser = argparse.ArgumentParser(description="Superset SQL Lab Cache Parser for DFIR")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--file", help="Parse a single cache file")
    group.add_argument("-d", "--directory", help="Parse a directory of raw cache files")
    parser.add_argument("-o", "--output", default="sqllab_timeline.csv", help="Output CSV filename and path")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    files_to_process = []
    
    if args.file:
        if os.path.isfile(args.file):
            files_to_process.append(args.file)
        else:
            print(f"[-] File not found: {args.file}")
            sys.exit(1)
    elif args.directory:
        if os.path.isdir(args.directory):
            for f in os.listdir(args.directory):
                full_path = os.path.join(args.directory, f)
                if os.path.isfile(full_path) and not full_path.endswith('.csv'):
                    files_to_process.append(full_path)
        else:
            print(f"[-] Directory not found: {args.directory}")
            sys.exit(1)

    records = []
    print(f"[*] Parsing {len(files_to_process)} file(s)...")
    
    for file_path in files_to_process:
        try:
            record = parse_cache_file(file_path)
            records.append(record)
        except Exception:
            pass

    if not records:
        print("[-] No records parsed. Exiting.")
        sys.exit(1)

    # Sort chronologically by start epoch timestamp
    records.sort(key=lambda x: (x["start_epoch_ms"], str(x["query_id"])))

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    fieldnames = ["Line", "Date/Time", "Source", "QueryID", "User", "Database", "Status", "SQL", "EndTime", "ResultPreview", "CacheKey"]
    
    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for idx, r in enumerate(records, start=1):
            # Map the parsed snake_case dictionary into the exact fieldnames required for the CSV
            row = {
                "Line": idx,
                "Date/Time": r.get("timestamp", ""),
                "Source": "Superset SQL Lab",
                "QueryID": r.get("query_id", ""),
                "User": r.get("user", ""),
                "Database": r.get("database", ""),
                "Status": r.get("status", ""),
                "SQL": r.get("sql", ""),
                "EndTime": r.get("end_time", ""),
                "ResultPreview": r.get("result_preview", ""),
                "CacheKey": r.get("cache_key", "")
            }
            writer.writerow(row)

    print(f"[+] Generated {args.output} ({len(records)} events) ordered by time.")

if __name__ == "__main__":
    main()
