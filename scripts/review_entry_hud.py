"""Compatibility entry point; the maintained report implementation is shared."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.report_entry_hud import FACT_FIELDS,compare,main,read,review,values

if __name__=='__main__':main()
