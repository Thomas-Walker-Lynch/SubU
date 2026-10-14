#!/usr/bin/env python3
"""
stage_StanleyPark.py

Minimal config wrapper for client 'StanleyPark'.
Calls the generic stage orchestrator with the chosen ifaces.
"""

from __future__ import annotations
from stage_client import stage_client_artifacts

CLIENT = "StanleyPark"
IFACES = ["x6","US"]  # keep this list minimal & declarative

if __name__ == "__main__":
  ok = stage_client_artifacts(
     CLIENT
    ,IFACES
  )
  raise SystemExit(0 if ok else 2)
