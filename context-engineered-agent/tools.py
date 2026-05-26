import os
import csv
import json
from collections import defaultdict

class ToolManager:
    def __init__(self, data_dir="data", memory_file="memory.json"):
        self.data_dir = data_dir
        self.memory_file = os.path.join(data_dir, memory_file)
        os.makedirs(self.data_dir, exist_ok=True)
        if not os.path.exists(self.memory_file):
            with open(self.memory_file, "w") as f:
                json.dump({}, f)

    def list_files(self):
        """Lists files in raw data directory."""
        return os.listdir(self.data_dir)

    def get_file_metadata(self, filename):
        """JIT tool: Reads file structural schema and lines without loading whole files."""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return {"error": f"File {filename} not found."}
        size = os.path.getsize(filepath)
        with open(filepath, "r") as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            line_count = 1 + sum(1 for _ in reader)
        return {
            "filename": filename,
            "size_bytes": size,
            "total_lines": line_count,
            "headers": headers
        }

    def read_file_chunk(self, filename, start_line, limit=10):
        """JIT tool: Reads specific window of a file to prevent token bloat."""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return {"error": f"File {filename} not found."}
        chunk = []
        with open(filepath, "r") as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            if headers:
                chunk.append(headers)
            for _ in range(start_line - 1):
                next(reader, None)
            for _ in range(limit):
                row = next(reader, None)
                if row is None:
                    break
                chunk.append(row)
        return {
            "chunk_lines": len(chunk),
            "data": chunk,
            "range": f"lines {start_line} to {start_line + len(chunk) - 2 if len(chunk) > 1 else start_line}"
        }

    def find_top_active_user(self, filename, user_column="user_id", metric_column="activity_score"):
        """Streams the CSV and returns only the top active user summary."""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return {"error": f"File {filename} not found."}

        activity_by_user = defaultdict(float)
        event_count_by_user = defaultdict(int)
        rows_scanned = 0

        with open(filepath, "r", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return {"error": f"File {filename} has no header row."}
            if user_column not in reader.fieldnames:
                return {"error": f"Missing user column '{user_column}'.", "headers": reader.fieldnames}

            use_metric = metric_column in reader.fieldnames
            for row in reader:
                rows_scanned += 1
                user_id = row.get(user_column, "").strip()
                if not user_id:
                    continue
                event_count_by_user[user_id] += 1
                if use_metric:
                    try:
                        activity_by_user[user_id] += float(row.get(metric_column, 0) or 0)
                    except ValueError:
                        activity_by_user[user_id] += 0
                else:
                    activity_by_user[user_id] += 1

        if not activity_by_user:
            return {"error": "No user activity rows found.", "rows_scanned": rows_scanned}

        top_user, top_score = max(activity_by_user.items(), key=lambda item: item[1])
        return {
            "top_user": top_user,
            "activity_score": round(top_score, 2),
            "event_count": event_count_by_user[top_user],
            "rows_scanned": rows_scanned,
            "metric": metric_column if use_metric else "event_count",
        }

    def aggregate_revenue(self, filename, revenue_column="revenue", event_column="event_type", event_value="transaction"):
        """Streams the CSV and returns a compact revenue aggregation."""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return {"error": f"File {filename} not found."}

        total_revenue = 0.0
        transaction_count = 0
        rows_scanned = 0

        with open(filepath, "r", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return {"error": f"File {filename} has no header row."}
            missing = [column for column in [revenue_column, event_column] if column not in reader.fieldnames]
            if missing:
                return {"error": f"Missing columns: {missing}", "headers": reader.fieldnames}

            for row in reader:
                rows_scanned += 1
                if row.get(event_column, "").strip().lower() != event_value.lower():
                    continue
                try:
                    total_revenue += float(row.get(revenue_column, 0) or 0)
                except ValueError:
                    continue
                transaction_count += 1

        return {
            "total_revenue": round(total_revenue, 2),
            "transaction_count": transaction_count,
            "rows_scanned": rows_scanned,
            "currency": "USD",
        }

    def write_note(self, key, value):
        """Structured Note-Taking Tool: Preserves agent knowledge persistent state."""
        data = {}
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    pass
        data[key] = value
        with open(self.memory_file, "w") as f:
            json.dump(data, f, indent=2)
        return {"status": "success", "message": f"Saved '{key}' to persistent memory."}

    def read_notes(self):
        """Reads all active agent notes."""
        if os.path.exists(self.memory_file):
            with open(self.memory_file, "r") as f:
                return json.load(f)
        return {}