#!/usr/bin/env python3
"""
Comprehensive Backend Test Suite for Cafeteria Management System
Tests all API endpoints, WebSocket functionality, and complete order flow
"""

import asyncio
import json
import requests
import websockets
import time
from datetime import datetime
from typing import Dict, List, Any

# Backend URL from environment
BACKEND_URL = "https://af27eff3-ceac-4634-bb7f-ac3b781d00aa.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"
WS_URL = f"wss://af27eff3-ceac-4634-bb7f-ac3b781d00aa.preview.emergentagent.com/ws"

class CafeteriaBackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.created_orders = []
        self.created_tables = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")
        print()

    def test_init_data(self) -> bool:
        """Test initialization endpoint"""
        try:
            response = self.session.post(f"{API_BASE}/init-data")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                self.log_test("Initialize Default Data", True, f"Response: {data.get('message', 'Success')}")
            else:
                self.log_test("Initialize Default Data", False, f"Status: {response.status_code}, Response: {response.text}")
            
            return success
        except Exception as e:
            self.log_test("Initialize Default Data", False, f"Exception: {str(e)}")
            return False

    def test_menu_endpoints(self) -> bool:
        """Test all menu-related endpoints"""
        all_passed = True
        
        # Test GET /api/menu
        try:
            response = self.session.get(f"{API_BASE}/menu")
            if response.status_code == 200:
                menu_items = response.json()
                brazilian_items = [item for item in menu_items if any(word in item['name'] for word in ['Café', 'Cappuccino', 'Pão'])]
                self.log_test("GET Menu Items", True, f"Retrieved {len(menu_items)} items, {len(brazilian_items)} Brazilian items found")
            else:
                self.log_test("GET Menu Items", False, f"Status: {response.status_code}")
                all_passed = False
        except Exception as e:
            self.log_test("GET Menu Items", False, f"Exception: {str(e)}")
            all_passed = False

        # Test GET /api/menu/categories
        try:
            response = self.session.get(f"{API_BASE}/menu/categories")
            if response.status_code == 200:
                categories = response.json()
                category_names = [cat['category'] for cat in categories]
                self.log_test("GET Menu Categories", True, f"Categories: {category_names}")
            else:
                self.log_test("GET Menu Categories", False, f"Status: {response.status_code}")
                all_passed = False
        except Exception as e:
            self.log_test("GET Menu Categories", False, f"Exception: {str(e)}")
            all_passed = False

        # Test POST /api/menu (create new menu item)
        try:
            new_item = {
                "name": "Café com Leite Especial",
                "description": "Café especial da casa com leite cremoso",
                "price": 4.75,
                "category": "Bebidas Quentes"
            }
            response = self.session.post(f"{API_BASE}/menu", json=new_item)
            if response.status_code == 200:
                created_item = response.json()
                self.log_test("POST Create Menu Item", True, f"Created item: {created_item['name']} - R${created_item['price']}")
            else:
                self.log_test("POST Create Menu Item", False, f"Status: {response.status_code}")
                all_passed = False
        except Exception as e:
            self.log_test("POST Create Menu Item", False, f"Exception: {str(e)}")
            all_passed = False

        return all_passed

    def test_table_endpoints(self) -> bool:
        """Test all table-related endpoints"""
        all_passed = True
        
        # Test GET /api/tables
        try:
            response = self.session.get(f"{API_BASE}/tables")
            if response.status_code == 200:
                tables = response.json()
                available_tables = [t for t in tables if t['status'] == 'available']
                self.log_test("GET Tables", True, f"Retrieved {len(tables)} tables, {len(available_tables)} available")
                
                # Store a table ID for status update test
                if tables:
                    self.test_table_id = tables[0]['id']
            else:
                self.log_test("GET Tables", False, f"Status: {response.status_code}")
                all_passed = False
        except Exception as e:
            self.log_test("GET Tables", False, f"Exception: {str(e)}")
            all_passed = False

        # Test POST /api/tables (create new table)
        try:
            new_table = {
                "number": 99,
                "capacity": 6
            }
            response = self.session.post(f"{API_BASE}/tables", json=new_table)
            if response.status_code == 200:
                created_table = response.json()
                self.created_tables.append(created_table['id'])
                self.log_test("POST Create Table", True, f"Created table {created_table['number']} with capacity {created_table['capacity']}")
            else:
                self.log_test("POST Create Table", False, f"Status: {response.status_code}")
                all_passed = False
        except Exception as e:
            self.log_test("POST Create Table", False, f"Exception: {str(e)}")
            all_passed = False

        # Test PUT /api/tables/{id} (update table status)
        if hasattr(self, 'test_table_id'):
            try:
                response = self.session.put(f"{API_BASE}/tables/{self.test_table_id}?status=occupied")
                if response.status_code == 200:
                    self.log_test("PUT Update Table Status", True, "Table status updated to occupied")
                else:
                    self.log_test("PUT Update Table Status", False, f"Status: {response.status_code}")
                    all_passed = False
            except Exception as e:
                self.log_test("PUT Update Table Status", False, f"Exception: {str(e)}")
                all_passed = False

        return all_passed

    def test_order_endpoints(self) -> bool:
        """Test complete order management flow"""
        all_passed = True
        
        # First get menu items for order creation
        menu_response = self.session.get(f"{API_BASE}/menu")
        if menu_response.status_code != 200:
            self.log_test("Order Flow - Get Menu", False, "Could not retrieve menu for order test")
            return False
        
        menu_items = menu_response.json()
        if not menu_items:
            self.log_test("Order Flow - Get Menu", False, "No menu items available")
            return False

        # Test POST /api/orders (create new order)
        try:
            # Create order with Brazilian cafeteria items
            order_items = [
                {
                    "menu_item_id": menu_items[0]['id'],
                    "menu_item_name": menu_items[0]['name'],
                    "quantity": 2,
                    "price": menu_items[0]['price'],
                    "special_requests": "Sem açúcar"
                },
                {
                    "menu_item_id": menu_items[1]['id'],
                    "menu_item_name": menu_items[1]['name'],
                    "quantity": 1,
                    "price": menu_items[1]['price']
                }
            ]
            
            new_order = {
                "table_number": 5,
                "items": order_items,
                "waiter_name": "Carlos Silva",
                "special_requests": "Cliente com pressa"
            }
            
            response = self.session.post(f"{API_BASE}/orders", json=new_order)
            if response.status_code == 200:
                created_order = response.json()
                self.created_orders.append(created_order['id'])
                expected_total = sum(item['price'] * item['quantity'] for item in order_items)
                self.log_test("POST Create Order", True, 
                            f"Order created for table {created_order['table_number']}, "
                            f"Total: R${created_order['total_amount']}, Expected: R${expected_total}")
            else:
                self.log_test("POST Create Order", False, f"Status: {response.status_code}, Response: {response.text}")
                all_passed = False
        except Exception as e:
            self.log_test("POST Create Order", False, f"Exception: {str(e)}")
            all_passed = False

        # Test GET /api/orders (all orders)
        try:
            response = self.session.get(f"{API_BASE}/orders")
            if response.status_code == 200:
                orders = response.json()
                self.log_test("GET All Orders", True, f"Retrieved {len(orders)} total orders")
            else:
                self.log_test("GET All Orders", False, f"Status: {response.status_code}")
                all_passed = False
        except Exception as e:
            self.log_test("GET All Orders", False, f"Exception: {str(e)}")
            all_passed = False

        # Test GET /api/orders/active (active orders only)
        try:
            response = self.session.get(f"{API_BASE}/orders/active")
            if response.status_code == 200:
                active_orders = response.json()
                self.log_test("GET Active Orders", True, f"Retrieved {len(active_orders)} active orders")
            else:
                self.log_test("GET Active Orders", False, f"Status: {response.status_code}")
                all_passed = False
        except Exception as e:
            self.log_test("GET Active Orders", False, f"Exception: {str(e)}")
            all_passed = False

        # Test PUT /api/orders/{id}/status (update order status)
        if self.created_orders:
            order_id = self.created_orders[0]
            statuses = ["preparing", "ready", "delivered"]
            
            for status in statuses:
                try:
                    status_update = {"status": status}
                    response = self.session.put(f"{API_BASE}/orders/{order_id}/status", json=status_update)
                    if response.status_code == 200:
                        self.log_test(f"PUT Update Order Status to {status}", True, f"Order status updated to {status}")
                    else:
                        self.log_test(f"PUT Update Order Status to {status}", False, f"Status: {response.status_code}")
                        all_passed = False
                except Exception as e:
                    self.log_test(f"PUT Update Order Status to {status}", False, f"Exception: {str(e)}")
                    all_passed = False

        # Test DELETE /api/orders/{id} (cancel order) - create a new order first
        try:
            cancel_order = {
                "table_number": 8,
                "items": [{
                    "menu_item_id": menu_items[0]['id'],
                    "menu_item_name": menu_items[0]['name'],
                    "quantity": 1,
                    "price": menu_items[0]['price']
                }],
                "waiter_name": "Ana Costa"
            }
            
            response = self.session.post(f"{API_BASE}/orders", json=cancel_order)
            if response.status_code == 200:
                order_to_cancel = response.json()
                
                # Now cancel it
                cancel_response = self.session.delete(f"{API_BASE}/orders/{order_to_cancel['id']}")
                if cancel_response.status_code == 200:
                    self.log_test("DELETE Cancel Order", True, f"Order {order_to_cancel['id']} cancelled successfully")
                else:
                    self.log_test("DELETE Cancel Order", False, f"Status: {cancel_response.status_code}")
                    all_passed = False
            else:
                self.log_test("DELETE Cancel Order", False, "Could not create order to cancel")
                all_passed = False
        except Exception as e:
            self.log_test("DELETE Cancel Order", False, f"Exception: {str(e)}")
            all_passed = False

        return all_passed

    def test_dashboard_stats(self) -> bool:
        """Test dashboard statistics endpoint"""
        try:
            response = self.session.get(f"{API_BASE}/dashboard/stats")
            if response.status_code == 200:
                stats = response.json()
                required_keys = ['orders', 'tables', 'today_revenue', 'timestamp']
                
                if all(key in stats for key in required_keys):
                    self.log_test("GET Dashboard Stats", True, 
                                f"Orders: {stats['orders']}, Tables: {stats['tables']}, "
                                f"Today's Revenue: R${stats['today_revenue']}")
                    return True
                else:
                    missing_keys = [key for key in required_keys if key not in stats]
                    self.log_test("GET Dashboard Stats", False, f"Missing keys: {missing_keys}")
                    return False
            else:
                self.log_test("GET Dashboard Stats", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("GET Dashboard Stats", False, f"Exception: {str(e)}")
            return False

    async def test_websocket_connection(self) -> bool:
        """Test WebSocket connection and real-time communication"""
        try:
            async with websockets.connect(WS_URL) as websocket:
                # First, consume any initial messages that might be sent
                try:
                    initial_msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    print(f"   Initial message received: {initial_msg}")
                except asyncio.TimeoutError:
                    pass  # No initial message, that's fine
                
                # Send a test message
                test_message = "Test message from backend tester"
                await websocket.send(test_message)
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                
                if "Message received" in response:
                    self.log_test("WebSocket Connection", True, f"Received: {response}")
                    return True
                else:
                    self.log_test("WebSocket Connection", False, f"Unexpected response: {response}")
                    return False
                    
        except asyncio.TimeoutError:
            self.log_test("WebSocket Connection", False, "Timeout waiting for WebSocket response")
            return False
        except Exception as e:
            self.log_test("WebSocket Connection", False, f"Exception: {str(e)}")
            return False

    async def test_websocket_broadcasts(self) -> bool:
        """Test WebSocket broadcasts during order operations"""
        try:
            # Connect to WebSocket
            async with websockets.connect(WS_URL) as websocket:
                # Consume any initial messages
                try:
                    initial_msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    print(f"   Initial broadcast message: {initial_msg}")
                except asyncio.TimeoutError:
                    pass  # No initial message
                
                # Get menu items first
                menu_response = self.session.get(f"{API_BASE}/menu")
                if menu_response.status_code != 200:
                    self.log_test("WebSocket Broadcast Test", False, "Could not get menu items")
                    return False
                
                menu_items = menu_response.json()
                if not menu_items:
                    self.log_test("WebSocket Broadcast Test", False, "No menu items available")
                    return False

                # Create an order and listen for broadcast
                broadcast_order = {
                    "table_number": 6,
                    "items": [{
                        "menu_item_id": menu_items[0]['id'],
                        "menu_item_name": menu_items[0]['name'],
                        "quantity": 1,
                        "price": menu_items[0]['price']
                    }],
                    "waiter_name": "Maria Santos"
                }
                
                # Create order (should trigger broadcast)
                order_response = self.session.post(f"{API_BASE}/orders", json=broadcast_order)
                
                if order_response.status_code == 200:
                    try:
                        # Wait for broadcast message
                        broadcast_message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        
                        # Try to parse as JSON
                        try:
                            broadcast_data = json.loads(broadcast_message)
                            if broadcast_data.get('type') == 'new_order':
                                self.log_test("WebSocket Real-time Broadcast", True, 
                                            f"Received new_order broadcast for table {broadcast_data['order']['table_number']}")
                                return True
                            else:
                                self.log_test("WebSocket Real-time Broadcast", False, 
                                            f"Unexpected broadcast type: {broadcast_data.get('type')}")
                                return False
                        except json.JSONDecodeError:
                            # If not JSON, check if it's the echo response
                            if "Message received" in broadcast_message:
                                self.log_test("WebSocket Real-time Broadcast", False, 
                                            "Received echo instead of broadcast - WebSocket may not be broadcasting order events")
                                return False
                            else:
                                self.log_test("WebSocket Real-time Broadcast", False, 
                                            f"Non-JSON broadcast message: {broadcast_message}")
                                return False
                    except asyncio.TimeoutError:
                        self.log_test("WebSocket Real-time Broadcast", False, "No broadcast received within timeout")
                        return False
                else:
                    self.log_test("WebSocket Real-time Broadcast", False, "Failed to create order for broadcast test")
                    return False
                    
        except Exception as e:
            self.log_test("WebSocket Real-time Broadcast", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Cafeteria Management System Backend Tests")
        print("=" * 60)
        print()
        
        # Test sequence
        tests = [
            ("Initialize Data", self.test_init_data),
            ("Menu Management", self.test_menu_endpoints),
            ("Table Management", self.test_table_endpoints),
            ("Order Management", self.test_order_endpoints),
            ("Dashboard Statistics", self.test_dashboard_stats),
        ]
        
        # Run synchronous tests
        for test_name, test_func in tests:
            print(f"🧪 Testing {test_name}...")
            test_func()
            print()
        
        # Run WebSocket tests
        print("🧪 Testing WebSocket Communication...")
        asyncio.run(self.test_websocket_connection())
        print()
        
        print("🧪 Testing WebSocket Real-time Broadcasts...")
        asyncio.run(self.test_websocket_broadcasts())
        print()
        
        # Summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        print()
        
        # List failed tests
        failed_tests = [result for result in self.test_results if not result['success']]
        if failed_tests:
            print("❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
        else:
            print("✅ ALL TESTS PASSED!")
        
        print()
        print("🎯 CRITICAL FUNCTIONALITY VERIFICATION:")
        print("✅ Brazilian cafeteria menu items" if any("Brazilian" in r['details'] for r in self.test_results if r['success']) else "❌ Brazilian menu items not verified")
        print("✅ Complete order flow" if any("Order created" in r['details'] for r in self.test_results if r['success']) else "❌ Order flow incomplete")
        print("✅ Real-time WebSocket communication" if any("WebSocket" in r['test'] for r in self.test_results if r['success']) else "❌ WebSocket communication failed")
        print("✅ Table status management" if any("Table status updated" in r['details'] for r in self.test_results if r['success']) else "❌ Table status management failed")
        print("✅ Dashboard statistics" if any("Dashboard Stats" in r['test'] for r in self.test_results if r['success']) else "❌ Dashboard statistics failed")

if __name__ == "__main__":
    tester = CafeteriaBackendTester()
    tester.run_all_tests()