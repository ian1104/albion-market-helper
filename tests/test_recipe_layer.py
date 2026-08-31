from pathlib import Path
from tempfile import TemporaryDirectory

from db.database import Database
from services.crafting_strategy import CraftingStrategy
from services.recipe_data import Recipe, RecipeMaterial, RecipeRepository

def test_recipe_persistence_and_material_relationship():
    with TemporaryDirectory() as tmp:
        db=Database(Path(tmp)/'market.db'); repo=RecipeRepository(db)
        recipe=Recipe('T4_TEST','T4_TEST',1,(RecipeMaterial('T4_MAT',4),),tier=4)
        assert repo.replace([recipe])==1
        loaded=repo.get('T4_TEST'); assert loaded is not None
        assert loaded.materials[0].item_id=='T4_MAT'; assert loaded.materials[0].quantity==4

def test_crafting_scanner_uses_market_data_and_production_rule():
    with TemporaryDirectory() as tmp:
        db=Database(Path(tmp)/'market.db')
        db.rows=[
            {'item_id':'T4_MAT','city':'Fort Sterling','sell_price_min':100,'buy_price_max':90,'sell_price_min_date':'2026-08-31T00:00:00Z','buy_price_max_date':'2026-08-31T00:00:00Z'},
            {'item_id':'T4_TEST','city':'Fort Sterling','sell_price_min':500,'buy_price_max':450,'sell_price_min_date':'2026-08-31T00:00:00Z','buy_price_max_date':'2026-08-31T00:00:00Z'},
        ]
        repo=RecipeRepository(db); repo.replace([Recipe('T4_TEST','T4_TEST',1,(RecipeMaterial('T4_MAT',4),),tier=4,crafting_time_minutes=1,focus_cost=10)])
        result=CraftingStrategy(db,repo).evaluate(server='east',city='Fort Sterling',station_fee=10)
        assert len(result)==1; assert result[0].expected_profit is not None; assert result[0].roi_percent is not None; assert result[0].profit_per_hour is not None

def test_unknown_station_fee_does_not_create_fake_opportunity():
    with TemporaryDirectory() as tmp:
        db=Database(Path(tmp)/'market.db'); repo=RecipeRepository(db)
        repo.replace([Recipe('T4_TEST','T4_TEST',1,(RecipeMaterial('T4_MAT',4),),tier=4)])
        assert CraftingStrategy(db,repo).evaluate(server='east',city='Fort Sterling')==[]
