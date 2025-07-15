from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
from enum import Enum


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove broken connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# Enums
class OrderStatus(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class TableStatus(str, Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"

# Models
class MenuItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    price: float
    category: str
    image: Optional[str] = None
    available: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MenuItemCreate(BaseModel):
    name: str
    description: str
    price: float
    category: str
    image: Optional[str] = None

class Table(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    number: int
    status: TableStatus = TableStatus.AVAILABLE
    capacity: int
    current_customers: int = 0

class TableCreate(BaseModel):
    number: int
    capacity: int

class OrderItem(BaseModel):
    menu_item_id: str
    menu_item_name: str
    quantity: int
    price: float
    special_requests: Optional[str] = None

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    table_number: int
    items: List[OrderItem]
    status: OrderStatus = OrderStatus.PENDING
    total_amount: float
    waiter_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    special_requests: Optional[str] = None

class OrderCreate(BaseModel):
    table_number: int
    items: List[OrderItem]
    waiter_name: str
    special_requests: Optional[str] = None

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now (can be enhanced for specific message handling)
            await manager.send_personal_message(f"Message received: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Menu endpoints
@api_router.get("/menu", response_model=List[MenuItem])
async def get_menu():
    menu_items = await db.menu_items.find({"available": True}).to_list(1000)
    return [MenuItem(**item) for item in menu_items]

@api_router.post("/menu", response_model=MenuItem)
async def create_menu_item(item: MenuItemCreate):
    menu_item = MenuItem(**item.dict())
    await db.menu_items.insert_one(menu_item.dict())
    return menu_item

@api_router.get("/menu/categories")
async def get_menu_categories():
    pipeline = [
        {"$match": {"available": True}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    categories = await db.menu_items.aggregate(pipeline).to_list(100)
    return [{"category": cat["_id"], "count": cat["count"]} for cat in categories]

# Table endpoints
@api_router.get("/tables", response_model=List[Table])
async def get_tables():
    tables = await db.tables.find().sort("number", 1).to_list(1000)
    return [Table(**table) for table in tables]

@api_router.post("/tables", response_model=Table)
async def create_table(table: TableCreate):
    # Check if table number already exists
    existing = await db.tables.find_one({"number": table.number})
    if existing:
        raise HTTPException(status_code=400, detail="Table number already exists")
    
    new_table = Table(**table.dict())
    await db.tables.insert_one(new_table.dict())
    return new_table

@api_router.put("/tables/{table_id}")
async def update_table_status(table_id: str, status: TableStatus):
    result = await db.tables.update_one(
        {"id": table_id},
        {"$set": {"status": status}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Table not found")
    return {"message": "Table status updated"}

# Order endpoints
@api_router.get("/orders", response_model=List[Order])
async def get_orders():
    orders = await db.orders.find().sort("created_at", -1).to_list(1000)
    return [Order(**order) for order in orders]

@api_router.get("/orders/active", response_model=List[Order])
async def get_active_orders():
    active_statuses = [OrderStatus.PENDING, OrderStatus.PREPARING, OrderStatus.READY]
    orders = await db.orders.find({"status": {"$in": active_statuses}}).sort("created_at", 1).to_list(1000)
    return [Order(**order) for order in orders]

@api_router.post("/orders", response_model=Order)
async def create_order(order: OrderCreate):
    # Calculate total amount
    total = sum(item.price * item.quantity for item in order.items)
    
    # Create order
    new_order = Order(**order.dict(), total_amount=total)
    await db.orders.insert_one(new_order.dict())
    
    # Update table status to occupied
    await db.tables.update_one(
        {"number": order.table_number},
        {"$set": {"status": TableStatus.OCCUPIED}}
    )
    
    # Broadcast new order to all connected clients
    await manager.broadcast(json.dumps({
        "type": "new_order",
        "order": new_order.dict(),
        "timestamp": datetime.utcnow().isoformat()
    }, default=str))
    
    return new_order

@api_router.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, status_update: OrderStatusUpdate):
    result = await db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": status_update.status,
            "updated_at": datetime.utcnow()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get updated order
    order = await db.orders.find_one({"id": order_id})
    
    # If order is delivered, update table status
    if status_update.status == OrderStatus.DELIVERED:
        await db.tables.update_one(
            {"number": order["table_number"]},
            {"$set": {"status": TableStatus.AVAILABLE}}
        )
    
    # Broadcast status update
    await manager.broadcast(json.dumps({
        "type": "order_status_update",
        "order_id": order_id,
        "status": status_update.status,
        "table_number": order["table_number"],
        "timestamp": datetime.utcnow().isoformat()
    }))
    
    return {"message": "Order status updated"}

@api_router.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    # Get order first to get table number
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update order status to cancelled
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": OrderStatus.CANCELLED,
            "updated_at": datetime.utcnow()
        }}
    )
    
    # Update table status to available
    await db.tables.update_one(
        {"number": order["table_number"]},
        {"$set": {"status": TableStatus.AVAILABLE}}
    )
    
    # Broadcast cancellation
    await manager.broadcast(json.dumps({
        "type": "order_cancelled",
        "order_id": order_id,
        "table_number": order["table_number"],
        "timestamp": datetime.utcnow().isoformat()
    }))
    
    return {"message": "Order cancelled"}

# Dashboard stats
@api_router.get("/dashboard/stats")
async def get_dashboard_stats():
    # Count orders by status
    pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    order_stats = await db.orders.aggregate(pipeline).to_list(100)
    
    # Count tables by status
    table_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]
    table_stats = await db.tables.aggregate(table_pipeline).to_list(100)
    
    # Today's revenue
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    revenue_pipeline = [
        {"$match": {
            "created_at": {"$gte": today_start},
            "status": {"$in": [OrderStatus.DELIVERED]}
        }},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]
    revenue_result = await db.orders.aggregate(revenue_pipeline).to_list(1)
    today_revenue = revenue_result[0]["total"] if revenue_result else 0
    
    return {
        "orders": {stat["_id"]: stat["count"] for stat in order_stats},
        "tables": {stat["_id"]: stat["count"] for stat in table_stats},
        "today_revenue": today_revenue,
        "timestamp": datetime.utcnow().isoformat()
    }

# Initialize default data
@api_router.post("/init-data")
async def initialize_default_data():
    # Check if data already exists
    existing_menu = await db.menu_items.count_documents({})
    existing_tables = await db.tables.count_documents({})
    
    if existing_menu > 0 and existing_tables > 0:
        return {"message": "Data already initialized"}
    
    # Create default menu items
    default_menu = [
        {"name": "Café Expresso", "description": "Café forte e encorpado", "price": 3.50, "category": "Bebidas Quentes"},
        {"name": "Cappuccino", "description": "Café com leite vaporizado e espuma", "price": 5.00, "category": "Bebidas Quentes"},
        {"name": "Latte", "description": "Café com muito leite vaporizado", "price": 5.50, "category": "Bebidas Quentes"},
        {"name": "Mocha", "description": "Café com chocolate e chantilly", "price": 6.00, "category": "Bebidas Quentes"},
        {"name": "Suco de Laranja", "description": "Suco natural de laranja", "price": 4.00, "category": "Bebidas Frias"},
        {"name": "Smoothie de Frutas", "description": "Smoothie com frutas da estação", "price": 7.00, "category": "Bebidas Frias"},
        {"name": "Pão na Chapa", "description": "Pão francês na chapa com manteiga", "price": 4.50, "category": "Lanches"},
        {"name": "Sanduíche Natural", "description": "Sanduíche com peito de peru e salada", "price": 8.00, "category": "Lanches"},
        {"name": "Croissant", "description": "Croissant fresco com geleia", "price": 5.50, "category": "Lanches"},
        {"name": "Bolo de Chocolate", "description": "Fatia de bolo de chocolate caseiro", "price": 6.50, "category": "Sobremesas"},
        {"name": "Cheesecake", "description": "Cheesecake de frutas vermelhas", "price": 7.50, "category": "Sobremesas"},
        {"name": "Pudim", "description": "Pudim de leite condensado", "price": 5.00, "category": "Sobremesas"}
    ]
    
    menu_items = [MenuItem(**item) for item in default_menu]
    await db.menu_items.insert_many([item.dict() for item in menu_items])
    
    # Create default tables
    default_tables = [Table(number=i, capacity=4) for i in range(1, 11)]
    await db.tables.insert_many([table.dict() for table in default_tables])
    
    return {"message": "Default data initialized successfully"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
@app.get("/")
async def root():
    return {"message": "Backend online"}
@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
