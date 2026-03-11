from falkordb import FalkorDB
import time
import os
import subprocess

def run_gource(files_only=False, limit=10000, detailed=False):
    db = FalkorDB(host='localhost', port=6379)
    g = db.select_graph('codegraph')

    print("Generating custom Gource log from CodeGraph...")
    log_entries = []
    base_time = int(time.time()) - 1000000 
    time_step = 10
    current_time = base_time
    
    repo_res = g.query("MATCH (r:Repository) RETURN r.name LIMIT 1").result_set
    repo_name = repo_res[0][0] if repo_res else "Project"

    def path_for(*parts):
        if not parts:
            return "/" + repo_name
        out = []
        for p in parts:
            if not p:
                continue
            s = str(p).replace("\\", "/").lstrip("./")
            if repo_name in s:
                s = s.split(repo_name, 1)[-1].lstrip("/")
            out.append(s)
        return repo_name + "/" + "/".join(out)  # No leading slash for Gource

    if detailed:
        limit = 100000  # Export everything for detailed view
    # 1. Add Files (blue)
    file_res = g.query(f"MATCH (f:File) RETURN f.path LIMIT {limit}").result_set
    for r in file_res:
        path = path_for(r[0])
        log_entries.append(f"{current_time}|File|A|{path}|0074D9")
        current_time += time_step

    if not files_only:
        # 2. Add Modules (gray) - imports
        mod_res = g.query(f"MATCH (m:Module) RETURN m.name LIMIT {limit // 4}").result_set
        for r in mod_res:
            path = path_for("Modules", r[0])
            log_entries.append(f"{current_time}|Module|A|{path}|888888")
            current_time += time_step

        # 3. Add Classes (red)
        class_res = g.query(f"MATCH (f:File)-[:CONTAINS]->(c:Class) RETURN f.path, c.name LIMIT {limit}").result_set
        for r in class_res:
            path = path_for(r[0], r[1])
            log_entries.append(f"{current_time}|Class|A|{path}|FF4136")
            current_time += time_step

        # 4. Add Functions (green)
        fn_res = g.query(f"MATCH (f:File)-[:CONTAINS]->(fn:Function) RETURN f.path, fn.name LIMIT {limit}").result_set
        for r in fn_res:
            path = path_for(r[0], r[1])
            log_entries.append(f"{current_time}|Function|A|{path}|2ECC40")
            current_time += time_step

        # 5. Add Methods (yellow)
        m_res = g.query(f"""
            MATCH (c:Class)-[:CONTAINS]->(m:Method)
            MATCH (f:File)-[:CONTAINS]->(c)
            RETURN f.path, c.name, m.name LIMIT {limit}
        """).result_set
        for r in m_res:
            path = path_for(r[0], r[1], r[2])
            log_entries.append(f"{current_time}|Method|A|{path}|FFDC00")
            current_time += time_step

    else:
        print("  (files-only mode)")

    log_path = "gource_custom.log"
    with open(log_path, "w") as f:
        f.write("\n".join(log_entries))
        
    print(f"Exported {len(log_entries)} nodes to {log_path}.")
    print("Launching Gource...")
    
    try:
        # Slower animation + nodes stay visible longer for detailed view
        speed = "0.1" if detailed else "0.2"
        font_scale = "1.4" if detailed else "1.2"
        idle_time = "300" if detailed else "120"  # 5 min for detailed, 2 min default
        cmd = [
            "gource",
            "--log-format", "custom",
            log_path,
            "-s", speed,
            "--auto-skip-seconds", "0.01",
            "--file-idle-time", idle_time,
            "--seconds-per-day", "2" if detailed else "0.5",  # Slower progression for full visualization
            "--max-file-lag", "0.01",
            "--title", f"{repo_name} CodeGraph — Blue=File  Red=Class  Green=Function  Yellow=Method",
            "--key",
            "--file-extensions",
            "--font-scale", font_scale,
        ]
        subprocess.run(cmd)
    except FileNotFoundError:
        print("\nError: Gource is not installed or not in your PATH.")
        print("Install it using: brew install gource")