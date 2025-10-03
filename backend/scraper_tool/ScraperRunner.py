import os
import json
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Dict, Any

# Configuration
LOG = False
FILENAME = "outputData.json"
COMPETITORS = ["TopCon", "Zeiss", "Canon", "OptoVue", "Nidek"]

# Ensure imports work in subprocesses regardless of CWD
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Always write output to the backend folder (one level up from scraper_tool)
OUTPUT_PATH = BASE_DIR.parent / FILENAME


def _scrape_one(comp_name: str, log: bool = False, per_task_timeout: int = 120) -> Dict[str, Any]:
    """
    Worker executed in a separate process:
    - Imports the right scraper module for the competitor
    - Runs News, Jobs, and Patents in parallel threads (separate Chrome instances)
    - Times out each subtask to fail fast
    """
    # Import locally inside the subprocess to avoid pickling/import issues on Windows
    import PatentScraper  # type: ignore

    # Lazy module selection
    if comp_name == "TopCon":
        import TopConScraper as Mod  # type: ignore
    elif comp_name == "Zeiss":
        import ZeissScraper as Mod  # type: ignore
    elif comp_name == "Canon":
        import CanonScraper as Mod  # type: ignore
    elif comp_name == "OptoVue":
        import OptoVueScraper as Mod  # type: ignore
    elif comp_name == "Nidek":
        import NidekScraper as Mod  # type: ignore
    else:
        return {"Name": comp_name, "News": [], "Jobs": [], "Patents": []}

    result: Dict[str, Any] = {"Name": comp_name, "News": [], "Jobs": [], "Patents": []}

    def _safe_news():
        try:
            return Mod.runNews(log).get("News", [])
        except Exception:
            return []

    def _safe_jobs():
        try:
            return Mod.runJobs(log).get("Jobs", [])
        except Exception:
            return []

    def _safe_patents():
        try:
            return PatentScraper.runPatent(comp_name).get("Patents", [])
        except Exception:
            return []

    # Execute tasks sequentially with per-task timeouts to avoid Chrome/driver conflicts
    from concurrent.futures import ThreadPoolExecutor as _TPE

    def run_with_timeout(fn, timeout):
        with _TPE(max_workers=1) as pool:
            fut = pool.submit(fn)
            try:
                return fut.result(timeout=timeout)
            except Exception:
                return []

    # Run News first (most visible failure), then Jobs, then Patents
    result["News"] = run_with_timeout(_safe_news, per_task_timeout)
    result["Jobs"] = run_with_timeout(_safe_jobs, per_task_timeout)
    result["Patents"] = run_with_timeout(_safe_patents, per_task_timeout)

    # Optional: cap items to bound payload size (tune as needed)
    if isinstance(result.get("News"), list):
        result["News"] = result["News"][:10]
    if isinstance(result.get("Jobs"), list):
        result["Jobs"] = result["Jobs"][:10]
    if isinstance(result.get("Patents"), list):
        result["Patents"] = result["Patents"][:5]

    return result


def main() -> None:
    data = {"Competitor": []}
    # Parallelize across competitors using processes (Selenium is not thread-safe)
    max_workers = min(3, len(COMPETITORS), (os.cpu_count() or 3))
    per_competitor_timeout = 300  # seconds

    results_by_name: Dict[str, Dict[str, Any]] = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_scrape_one, name, LOG): name for name in COMPETITORS}
        for fut, name in list(future_map.items()):
            try:
                res = fut.result(timeout=per_competitor_timeout)
            except Exception:
                res = {"Name": name, "News": [], "Jobs": [], "Patents": []}
            results_by_name[name] = res

    # Preserve UI order
    for name in COMPETITORS:
        data["Competitor"].append(results_by_name.get(name, {"Name": name, "News": [], "Jobs": [], "Patents": []}))

    # Write output atomically-ish
    try:
        if OUTPUT_PATH.exists():
            OUTPUT_PATH.unlink()
    except Exception:
        # Ignore delete failures; we'll overwrite
        pass

    with open(OUTPUT_PATH, "w", encoding="utf-8") as write:
        json.dump(data, write, ensure_ascii=False)


if __name__ == "__main__":
    main()