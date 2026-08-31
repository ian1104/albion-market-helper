from __future__ import annotations

import argparse

from db.database import Database
from services.recipe_data import AOBinDumpRecipeProvider, RecipeRepository

def main() -> int:
    parser=argparse.ArgumentParser(description='Sync normalized Albion recipes from ao-bin-dumps.')
    parser.add_argument('--source-url',default=None); args=parser.parse_args()
    provider=AOBinDumpRecipeProvider(source_url=args.source_url) if args.source_url else AOBinDumpRecipeProvider()
    repository=RecipeRepository(Database()); count=repository.replace(provider.load())
    print(f'synced_recipes={count}'); print(f'stored_recipes={repository.count()}'); return 0

if __name__=='__main__': raise SystemExit(main())
