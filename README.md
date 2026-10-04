# Superset SQL Lab Cache Parser

A Digital Forensics and Incident Response (DFIR) script that parses raw Apache Superset SQL Lab cache files. It natively decompresses the data and outputs a chronologically ordered CSV timeline containing the executed SQL queries, usernames, target databases, and timestamps.

### 1. Installation

Clone the repository and install the required dependencies:

```bash
git clone https://github.com/abubker99/superset-sqllab-parser.git
cd superset-sqllab-parser
pip install -r requirements.txt
```

### 2. Usage

Run the tool against a single file or a directory. 

**Parse a directory of cache files:**
```bash
python3 sqllab_parser.py -d /path/to/cache/folder
```

**Parse a single file:**
```bash
python3 sqllab_parser.py -f /path/to/file
```

**Specify a custom output path (default is sqllab_timeline.csv):**
```bash
python3 sqllab_parser.py -d /path/to/cache/folder -o /custom/path/timeline.csv
```

**View the help menu:**
```bash
python3 sqllab_parser.py -h
```
