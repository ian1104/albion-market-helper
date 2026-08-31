from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

import httpx

DEFAULT_RECIPE_SOURCE = os.getenv("ALBION_RECIPE_SOURCE_URL", "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/items.json")
SPECIALTY_CITY_BY_CATEGORY = {"offhands":"Martlock","bags":"Brecilien","capes":"Brecilien","gathering":"Caerleon"}
SPECIALTY_CITY_BY_SUBCATEGORY = {"sword":"Lymhurst","bow":"Lymhurst","arcanestaff":"Lymhurst","axe":"Martlock","quarterstaff":"Martlock","froststaff":"Martlock","mace":"Thetford","firestaff":"Thetford","naturestaff":"Thetford","hammer":"Fort Sterling","spear":"Fort Sterling","holystaff":"Fort Sterling","crossbow":"Bridgewatch","dagger":"Bridgewatch","cursestaff":"Bridgewatch","knuckles":"Caerleon","shapeshifterstaff":"Caerleon","cloth_armor":"Fort Sterling","plate_helmet":"Fort Sterling","leather_helmet":"Lymhurst","leather_shoes":"Lymhurst","plate_armor":"Bridgewatch","cloth_shoes":"Bridgewatch","leather_armor":"Thetford","cloth_helmet":"Thetford","plate_shoes":"Martlock"}

def _specialty_city(item: dict[str, Any]) -> str | None:
    category=item.get("@shopcategory") or item.get("shopCategory")
    if category in SPECIALTY_CITY_BY_CATEGORY:return SPECIALTY_CITY_BY_CATEGORY[category]
    subcategory=item.get("@shopsubcategory1") or item.get("shopSubcategory1")
    return SPECIALTY_CITY_BY_SUBCATEGORY.get(subcategory)

@dataclass(frozen=True)
class RecipeMaterial:
    item_id: str
    quantity: float
    returnable: bool = True
@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    output_item_id: str
    output_quantity: float
    materials: tuple[RecipeMaterial, ...]
    category: str | None = None
    tier: int | None = None
    enchantment: int = 0
    crafting_time_minutes: float | None = None
    focus_cost: float | None = None
    source: str = "unknown"
    source_version: str | None = None
    updated_at: str | None = None
    specialty_city: str | None = None
class RecipeProvider(Protocol):
    def load(self) -> Iterable[Recipe]: ...
class AOBinDumpRecipeProvider:
    def __init__(self, source_url: str = DEFAULT_RECIPE_SOURCE, timeout: float = 60.0): self.source_url=source_url; self.timeout=timeout
    @staticmethod
    def _float(value: Any) -> float | None:
        try:return float(value) if value is not None else None
        except (TypeError,ValueError):return None
    @staticmethod
    def _item_id(resource: dict[str, Any]) -> str | None:
        uid=resource.get("@uniquename") or resource.get("uniqueName")
        if not uid:return None
        level=resource.get("@enchantmentlevel") or resource.get("enchantmentLevel")
        if level not in (None,"","0",0) and "@" not in str(uid):return f"{uid}@{level}"
        return str(uid)
    @classmethod
    def _materials(cls, requirement: dict[str, Any]) -> tuple[RecipeMaterial,...]:
        raw=requirement.get("craftresource") or requirement.get("craftResourceList") or []
        if isinstance(raw,dict):
            if any(str(k).startswith("@uniquename") for k in raw):
                numbered=[]
                for key,value in raw.items():
                    if str(key).startswith("@uniquename"):
                        suffix=str(key)[len("@uniquename"):]; numbered.append({"@uniquename":value,"@count":raw.get(f"@count{suffix}")})
                raw=numbered
            else:raw=[raw]
        result=[]
        for resource in raw:
            if not isinstance(resource,dict):continue
            item_id=cls._item_id(resource); quantity=cls._float(resource.get("@count",resource.get("count")))
            if item_id and quantity and quantity>0:result.append(RecipeMaterial(item_id,quantity,resource.get("@maxreturnamount") not in ("0",0)))
        return tuple(result)
    @staticmethod
    def _tier(item_id: str) -> int | None:
        try:
            prefix=item_id.split("_",1)[0]; return int(prefix[1:]) if prefix.startswith("T") else None
        except (ValueError,IndexError):return None
    @staticmethod
    def _enchantment(item_id: str) -> int:
        try:return int(item_id.rsplit("@",1)[1]) if "@" in item_id else 0
        except ValueError:return 0
    @staticmethod
    def _iter_items(payload: dict[str,Any]) -> Iterable[dict[str,Any]]:
        root=payload.get("items",payload)
        if isinstance(root,list):yield from (x for x in root if isinstance(x,dict)); return
        if isinstance(root,dict):
            for value in root.values():
                if isinstance(value,list):yield from (x for x in value if isinstance(x,dict))
    def load(self) -> Iterable[Recipe]:
        with httpx.Client(timeout=self.timeout,follow_redirects=True) as client:
            response=client.get(self.source_url); response.raise_for_status(); payload=response.json()
        source_version=response.headers.get("etag") or response.headers.get("last-modified"); updated_at=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
        for item in self._iter_items(payload):
            output_id=item.get("@uniquename") or item.get("uniqueName")
            if not output_id or item.get("@showinmarketplace")=="false":continue
            requirements=item.get("craftingrequirements") or item.get("craftingRequirements")
            if isinstance(requirements,list):requirements=requirements[0] if requirements else None
            if not isinstance(requirements,dict):continue
            materials=self._materials(requirements)
            if not materials:continue
            yield Recipe(recipe_id=str(output_id),output_item_id=str(output_id),output_quantity=self._float(requirements.get("@amountcrafted",requirements.get("amountCrafted"))) or 1.0,materials=materials,category=item.get("@shopcategory") or item.get("shopCategory"),tier=self._tier(str(output_id)),enchantment=self._enchantment(str(output_id)),crafting_time_minutes=self._float(requirements.get("@time",requirements.get("time"))),focus_cost=self._float(requirements.get("@craftingfocus",requirements.get("craftingFocus"))),source="ao-bin-dumps",source_version=source_version,updated_at=updated_at,specialty_city=_specialty_city(item))
class RecipeRepository:
    def __init__(self,database:Any):self.path=Path(database.path);self.initialize()
    def _connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);conn=sqlite3.connect(self.path);conn.row_factory=sqlite3.Row;return conn
    def initialize(self):
        with self._connect() as conn:conn.executescript("""CREATE TABLE IF NOT EXISTS recipe_items(item_id TEXT PRIMARY KEY,localized_name TEXT,tier INTEGER,enchantment INTEGER NOT NULL DEFAULT 0,category TEXT,craftable INTEGER NOT NULL DEFAULT 1,tradable INTEGER NOT NULL DEFAULT 1,source TEXT NOT NULL,source_version TEXT,updated_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS recipes(recipe_id TEXT PRIMARY KEY,output_item_id TEXT NOT NULL,output_quantity REAL NOT NULL,category TEXT,tier INTEGER,enchantment INTEGER NOT NULL DEFAULT 0,crafting_time_minutes REAL,focus_cost REAL,specialty_city TEXT,source TEXT NOT NULL,source_version TEXT,updated_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS recipe_materials(recipe_id TEXT NOT NULL,material_item_id TEXT NOT NULL,quantity REAL NOT NULL,returnable INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(recipe_id,material_item_id),FOREIGN KEY(recipe_id) REFERENCES recipes(recipe_id) ON DELETE CASCADE);CREATE INDEX IF NOT EXISTS idx_recipes_scan ON recipes(tier,category,output_item_id);CREATE INDEX IF NOT EXISTS idx_recipe_materials_item ON recipe_materials(material_item_id);""")
    def replace(self,recipes:Iterable[Recipe])->int:
        self.initialize();count=0
        with self._connect() as conn:
            for recipe in recipes:
                updated=recipe.updated_at or datetime.now(timezone.utc).isoformat().replace("+00:00","Z");conn.execute("DELETE FROM recipe_materials WHERE recipe_id=?",(recipe.recipe_id,));conn.execute("""INSERT INTO recipes(recipe_id,output_item_id,output_quantity,category,tier,enchantment,crafting_time_minutes,focus_cost,specialty_city,source,source_version,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(recipe_id) DO UPDATE SET output_item_id=excluded.output_item_id,output_quantity=excluded.output_quantity,category=excluded.category,tier=excluded.tier,enchantment=excluded.enchantment,crafting_time_minutes=excluded.crafting_time_minutes,focus_cost=excluded.focus_cost,specialty_city=excluded.specialty_city,source=excluded.source,source_version=excluded.source_version,updated_at=excluded.updated_at""",(recipe.recipe_id,recipe.output_item_id,recipe.output_quantity,recipe.category,recipe.tier,recipe.enchantment,recipe.crafting_time_minutes,recipe.focus_cost,recipe.specialty_city,recipe.source,recipe.source_version,updated));conn.executemany("INSERT INTO recipe_materials(recipe_id,material_item_id,quantity,returnable) VALUES(?,?,?,?)",[(recipe.recipe_id,m.item_id,m.quantity,int(m.returnable)) for m in recipe.materials]);conn.execute("""INSERT INTO recipe_items(item_id,tier,enchantment,category,craftable,tradable,source,source_version,updated_at) VALUES(?,?,?,?,1,1,?,?,?) ON CONFLICT(item_id) DO UPDATE SET tier=excluded.tier,enchantment=excluded.enchantment,category=excluded.category,craftable=1,source=excluded.source,source_version=excluded.source_version,updated_at=excluded.updated_at""",(recipe.output_item_id,recipe.tier,recipe.enchantment,recipe.category,recipe.source,recipe.source_version,updated));count+=1
        return count
    @staticmethod
    def _tier(item_id):
        try:prefix=item_id.split("_",1)[0];return int(prefix[1:]) if prefix.startswith("T") else None
        except (ValueError,IndexError):return None
    @staticmethod
    def _enchantment(item_id):
        try:return int(item_id.rsplit("@",1)[1]) if "@" in item_id else 0
        except ValueError:return 0
    def count(self):
        with self._connect() as conn:return int(conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0])
    def get(self,recipe_id):
        with self._connect() as conn:
            row=conn.execute("SELECT * FROM recipes WHERE recipe_id=?",(recipe_id,)).fetchone()
            if not row:return None
            mats=conn.execute("SELECT * FROM recipe_materials WHERE recipe_id=? ORDER BY material_item_id",(recipe_id,)).fetchall()
        return self._row_to_recipe(row,mats)
    def list(self,*,tier=None,category=None,limit=None):
        clauses=[];params=[]
        if tier is not None:clauses.append("tier=?");params.append(tier)
        if category:clauses.append("category=?");params.append(category)
        sql="SELECT * FROM recipes"+(" WHERE "+" AND ".join(clauses) if clauses else "")+" ORDER BY recipe_id"
        if limit is not None:sql+=" LIMIT ?";params.append(limit)
        with self._connect() as conn:
            rows=conn.execute(sql,params).fetchall()
            if not rows:return []
            ids=[r["recipe_id"] for r in rows];ph=",".join("?" for _ in ids);mats=conn.execute(f"SELECT * FROM recipe_materials WHERE recipe_id IN ({ph}) ORDER BY recipe_id,material_item_id",ids).fetchall()
        grouped={}
        for row in mats:grouped.setdefault(row["recipe_id"],[]).append(row)
        return [self._row_to_recipe(row,grouped.get(row["recipe_id"],[])) for row in rows]
    @staticmethod
    def _row_to_recipe(row,materials):
        return Recipe(recipe_id=row["recipe_id"],output_item_id=row["output_item_id"],output_quantity=row["output_quantity"],materials=tuple(RecipeMaterial(m["material_item_id"],m["quantity"],bool(m["returnable"])) for m in materials),category=row["category"],tier=row["tier"],enchantment=row["enchantment"],crafting_time_minutes=row["crafting_time_minutes"],focus_cost=row["focus_cost"],specialty_city=row["specialty_city"],source=row["source"],source_version=row["source_version"],updated_at=row["updated_at"])
