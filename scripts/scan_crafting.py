from __future__ import annotations

import argparse

from config import CITIES, ALBION_SERVER
from db.database import Database
from services.crafting_strategy import CraftingStrategy

def main() -> int:
    parser=argparse.ArgumentParser(description='Scan normalized recipes against stored market prices.')
    parser.add_argument('--server',default=ALBION_SERVER); parser.add_argument('--city',action='append',dest='cities')
    parser.add_argument('--capital',type=float); parser.add_argument('--station-fee',type=float,required=True)
    parser.add_argument('--use-focus',action='store_true'); parser.add_argument('--limit',type=int,default=20)
    parser.add_argument('--min-profit',type=float); parser.add_argument('--min-roi',type=float); args=parser.parse_args()
    cities=args.cities or list(CITIES); strategy=CraftingStrategy(Database()); rows=[]
    for city in cities:
        rows.extend(strategy.evaluate(server=args.server,city=city,capital=args.capital,station_fee=args.station_fee,use_focus=args.use_focus,min_profit=args.min_profit,min_roi=args.min_roi,scan_limit=10000))
    rows.sort(key=lambda x:x.expected_profit if x.expected_profit is not None else float('-inf'),reverse=True)
    for row in rows[:args.limit]: print(row.to_dict())
    print(f'opportunities={len(rows)}'); return 0

if __name__=='__main__': raise SystemExit(main())
