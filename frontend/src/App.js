import React, { useState, useEffect, useRef } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

// Mobile Detection
const isMobile = () => window.innerWidth <= 768;

// WebSocket Hook
const useWebSocket = (onMessage) => {
  const ws = useRef(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const connect = () => {
      ws.current = new WebSocket(`${WS_URL}/ws`);
      
      ws.current.onopen = () => {
        setIsConnected(true);
        console.log('WebSocket connected');
      };
      
      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch (e) {
          console.log('Received:', event.data);
        }
      };
      
      ws.current.onclose = () => {
        setIsConnected(false);
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(connect, 3000);
      };
      
      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };

    connect();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  return { isConnected };
};

// Waiter Interface (Mobile)
const WaiterInterface = ({ onOrderCreated }) => {
  const [menu, setMenu] = useState([]);
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [cart, setCart] = useState([]);
  const [waiterName, setWaiterName] = useState('');
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [specialRequests, setSpecialRequests] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    fetchMenu();
    fetchTables();
    fetchCategories();
  }, []);

  const fetchMenu = async () => {
    try {
      const response = await axios.get(`${API}/menu`);
      setMenu(response.data);
    } catch (error) {
      console.error('Error fetching menu:', error);
    }
  };

  const fetchTables = async () => {
    try {
      const response = await axios.get(`${API}/tables`);
      setTables(response.data);
    } catch (error) {
      console.error('Error fetching tables:', error);
    }
  };

  const fetchCategories = async () => {
    try {
      const response = await axios.get(`${API}/menu/categories`);
      setCategories([{ category: 'all', count: 0 }, ...response.data]);
    } catch (error) {
      console.error('Error fetching categories:', error);
    }
  };

  const addToCart = (item) => {
    const existingItem = cart.find(cartItem => cartItem.menu_item_id === item.id);
    if (existingItem) {
      setCart(cart.map(cartItem =>
        cartItem.menu_item_id === item.id
          ? { ...cartItem, quantity: cartItem.quantity + 1 }
          : cartItem
      ));
    } else {
      setCart([...cart, {
        menu_item_id: item.id,
        menu_item_name: item.name,
        quantity: 1,
        price: item.price
      }]);
    }
  };

  const removeFromCart = (itemId) => {
    const existingItem = cart.find(cartItem => cartItem.menu_item_id === itemId);
    if (existingItem && existingItem.quantity > 1) {
      setCart(cart.map(cartItem =>
        cartItem.menu_item_id === itemId
          ? { ...cartItem, quantity: cartItem.quantity - 1 }
          : cartItem
      ));
    } else {
      setCart(cart.filter(cartItem => cartItem.menu_item_id !== itemId));
    }
  };

  const submitOrder = async () => {
    if (!selectedTable || !waiterName || cart.length === 0) {
      alert('Por favor, selecione uma mesa, digite o nome do cliente e adicione itens ao pedido');
      return;
    }

    setIsSubmitting(true);
    try {
      const orderData = {
        table_number: selectedTable.number,
        items: cart,
        waiter_name: waiterName,
        special_requests: specialRequests || null
      };

      await axios.post(`${API}/orders`, orderData);
      
      // Clear form
      setCart([]);
      setSelectedTable(null);
      setSpecialRequests('');
      
      alert('Pedido enviado com sucesso!');
      onOrderCreated && onOrderCreated();
      fetchTables(); // Refresh tables to update status
    } catch (error) {
      console.error('Error creating order:', error);
      alert('Erro ao enviar pedido. Tente novamente.');
    }
    setIsSubmitting(false);
  };

  const getTotal = () => {
    return cart.reduce((total, item) => total + (item.price * item.quantity), 0);
  };

  const filteredMenu = selectedCategory === 'all' 
    ? menu 
    : menu.filter(item => item.category === selectedCategory);

  const availableTables = tables.filter(table => table.status === 'available');

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Header */}
      <div className="bg-amber-600 text-white p-4 sticky top-0 z-10">
        <h1 className="text-xl font-bold">🧑‍🍳 Interface do Garçom</h1>
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            placeholder="Nome do cliente"
            value={waiterName}
            onChange={(e) => setWaiterName(e.target.value)}
            className="flex-1 px-3 py-1 rounded text-black text-sm"
          />
        </div>
      </div>

      {/* Table Selection */}
      <div className="p-4 bg-white shadow-sm">
        <h2 className="font-semibold mb-3">Selecionar Mesa</h2>
        <div className="grid grid-cols-5 gap-2">
          {availableTables.map(table => (
            <button
              key={table.id}
              onClick={() => setSelectedTable(table)}
              className={`p-3 rounded-lg border-2 ${
                selectedTable?.id === table.id
                  ? 'border-amber-500 bg-amber-50'
                  : 'border-gray-200 bg-white'
              }`}
            >
              <div className="text-sm font-medium">Mesa {table.number}</div>
              <div className="text-xs text-gray-500">{table.capacity} lugares</div>
            </button>
          ))}
        </div>
      </div>

      {/* Category Filter */}
      <div className="p-4 bg-white shadow-sm">
        <div className="flex gap-2 overflow-x-auto">
          {categories.map(cat => (
            <button
              key={cat.category}
              onClick={() => setSelectedCategory(cat.category)}
              className={`px-4 py-2 rounded-full whitespace-nowrap text-sm ${
                selectedCategory === cat.category
                  ? 'bg-amber-500 text-white'
                  : 'bg-gray-100 text-gray-700'
              }`}
            >
              {cat.category === 'all' ? 'Todos' : cat.category}
            </button>
          ))}
        </div>
      </div>

      {/* Menu */}
      <div className="p-4">
        <h2 className="font-semibold mb-3">Cardápio</h2>
        <div className="space-y-3">
          {filteredMenu.map(item => (
            <div key={item.id} className="bg-white p-4 rounded-lg shadow-sm border">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <h3 className="font-medium">{item.name}</h3>
                  <p className="text-sm text-gray-600 mt-1">{item.description}</p>
                  <p className="text-amber-600 font-bold mt-2">R$ {item.price.toFixed(2)}</p>
                </div>
                <button
                  onClick={() => addToCart(item)}
                  className="ml-3 bg-amber-500 text-white px-3 py-1 rounded-lg text-sm font-medium"
                >
                  Adicionar
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Cart (Fixed Bottom) */}
      {cart.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg p-4">
          <div className="max-h-32 overflow-y-auto mb-3">
            {cart.map(item => (
              <div key={item.menu_item_id} className="flex justify-between items-center py-1">
                <span className="text-sm">{item.menu_item_name}</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => removeFromCart(item.menu_item_id)}
                    className="w-6 h-6 bg-red-500 text-white rounded-full text-xs"
                  >
                    -
                  </button>
                  <span className="text-sm">{item.quantity}</span>
                  <button
                    onClick={() => addToCart({ id: item.menu_item_id, name: item.menu_item_name, price: item.price })}
                    className="w-6 h-6 bg-green-500 text-white rounded-full text-xs"
                  >
                    +
                  </button>
                </div>
              </div>
            ))}
          </div>
          
          <div className="space-y-2">
            <input
              type="text"
              placeholder="Observações especiais"
              value={specialRequests}
              onChange={(e) => setSpecialRequests(e.target.value)}
              className="w-full px-3 py-2 border rounded text-sm"
            />
            
            <div className="flex justify-between items-center">
              <span className="font-bold">Total: R$ {getTotal().toFixed(2)}</span>
              <button
                onClick={submitOrder}
                disabled={isSubmitting}
                className="bg-green-500 text-white px-6 py-2 rounded-lg font-medium disabled:opacity-50"
              >
                {isSubmitting ? 'Enviando...' : 'Enviar Pedido'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Manager Interface (Desktop)
const ManagerInterface = () => {
  const [orders, setOrders] = useState([]);
  const [stats, setStats] = useState({});
  const [tables, setTables] = useState([]);

  useEffect(() => {
    fetchOrders();
    fetchStats();
    fetchTables();
    const interval = setInterval(() => {
      fetchOrders();
      fetchStats();
      fetchTables();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchOrders = async () => {
    try {
      const response = await axios.get(`${API}/orders/active`);
      setOrders(response.data);
    } catch (error) {
      console.error('Error fetching orders:', error);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchTables = async () => {
    try {
      const response = await axios.get(`${API}/tables`);
      setTables(response.data);
    } catch (error) {
      console.error('Error fetching tables:', error);
    }
  };

  const updateOrderStatus = async (orderId, newStatus) => {
    try {
      await axios.put(`${API}/orders/${orderId}/status`, { status: newStatus });
      fetchOrders();
      fetchTables();
    } catch (error) {
      console.error('Error updating order status:', error);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'pending': return 'bg-yellow-100 text-yellow-800';
      case 'preparing': return 'bg-blue-100 text-blue-800';
      case 'ready': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'pending': return 'Pendente';
      case 'preparing': return 'Preparando';
      case 'ready': return 'Pronto';
      case 'delivered': return 'Finalizado';
      default: return status;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">☕ Painel da Cafeteria</h1>
        <p className="text-gray-600">Gestão de pedidos em tempo real</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500">Pedidos Pendentes</h3>
          <p className="text-2xl font-bold text-yellow-600">{stats.orders?.pending || 0}</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500">Preparando</h3>
          <p className="text-2xl font-bold text-blue-600">{stats.orders?.preparing || 0}</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500">Prontos</h3>
          <p className="text-2xl font-bold text-green-600">{stats.orders?.ready || 0}</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-sm font-medium text-gray-500">Vendas Hoje</h3>
          <p className="text-2xl font-bold text-amber-600">R$ {(stats.today_revenue || 0).toFixed(2)}</p>
        </div>
      </div>

      {/* Tables Status */}
      <div className="bg-white p-6 rounded-lg shadow mb-8">
        <h2 className="text-xl font-bold mb-4">Status das Mesas</h2>
        <div className="grid grid-cols-5 md:grid-cols-10 gap-3">
          {tables.map(table => (
            <div
              key={table.id}
              className={`p-3 rounded-lg text-center text-sm font-medium ${
                table.status === 'available' 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}
            >
              <div>Mesa {table.number}</div>
              <div className="text-xs mt-1">
                {table.status === 'available' ? 'Livre' : 'Ocupada'}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Orders List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-6 border-b">
          <h2 className="text-xl font-bold">Pedidos Ativos</h2>
        </div>
        <div className="divide-y">
          {orders.map(order => (
            <div key={order.id} className="p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-bold text-lg">Mesa {order.table_number}</h3>
                  <p className="text-sm text-gray-600">Garçom: {order.waiter_name}</p>
                  <p className="text-sm text-gray-600">
                    {new Date(order.created_at).toLocaleTimeString('pt-BR')}
                  </p>
                </div>
                <div className="text-right">
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(order.status)}`}>
                    {getStatusText(order.status)}
                  </span>
                  <p className="font-bold text-lg mt-2">R$ {order.total_amount.toFixed(2)}</p>
                </div>
              </div>

              <div className="mb-4">
                <h4 className="font-medium mb-2">Itens:</h4>
                <div className="space-y-1">
                  {order.items.map((item, index) => (
                    <div key={index} className="flex justify-between text-sm">
                      <span>{item.quantity}x {item.menu_item_name}</span>
                      <span>R$ {(item.price * item.quantity).toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              </div>

              {order.special_requests && (
                <div className="mb-4 p-3 bg-yellow-50 rounded-lg">
                  <h4 className="font-medium text-sm">Observações:</h4>
                  <p className="text-sm">{order.special_requests}</p>
                </div>
              )}

              <div className="flex gap-2">
                {order.status === 'pending' && (
                  <button
                    onClick={() => updateOrderStatus(order.id, 'preparing')}
                    className="bg-blue-500 text-white px-4 py-2 rounded text-sm font-medium"
                  >
                    Iniciar Preparo
                  </button>
                )}
                {order.status === 'preparing' && (
                  <button
                    onClick={() => updateOrderStatus(order.id, 'ready')}
                    className="bg-green-500 text-white px-4 py-2 rounded text-sm font-medium"
                  >
                    Marcar como Pronto
                  </button>
                )}
                {order.status === 'ready' && (
                  <button
                    onClick={() => updateOrderStatus(order.id, 'delivered')}
                    className="bg-amber-500 text-white px-4 py-2 rounded text-sm font-medium"
                  >
                    Marcar como Finalizado
                  </button>
                )}
              </div>
            </div>
          ))}
          
          {orders.length === 0 && (
            <div className="p-8 text-center text-gray-500">
              Nenhum pedido ativo no momento
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Main App Component
const App = () => {
  const [view, setView] = useState(isMobile() ? 'waiter' : 'manager');
  const [orderUpdateTrigger, setOrderUpdateTrigger] = useState(0);

  // WebSocket message handler
  const handleWebSocketMessage = (data) => {
    if (data.type === 'new_order' || data.type === 'order_status_update') {
      setOrderUpdateTrigger(prev => prev + 1);
    }
  };

  const { isConnected } = useWebSocket(handleWebSocketMessage);

  // Initialize default data on first load
  useEffect(() => {
    const initializeData = async () => {
      try {
        await axios.post(`${API}/init-data`);
      } catch (error) {
        console.error('Error initializing data:', error);
      }
    };
    initializeData();
  }, []);

  return (
    <div className="App">
      {/* Connection Status */}
      <div className={`fixed top-2 right-2 z-50 px-3 py-1 rounded-full text-xs font-medium ${
        isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}>
        {isConnected ? '🟢 Conectado' : '🔴 Desconectado'}
      </div>

      {/* View Toggle (only show on desktop) */}
      {!isMobile() && (
        <div className="fixed top-2 left-2 z-50 bg-white rounded-lg shadow-lg p-2">
          <div className="flex gap-1">
            <button
              onClick={() => setView('waiter')}
              className={`px-3 py-1 rounded text-sm font-medium ${
                view === 'waiter' ? 'bg-amber-500 text-white' : 'text-gray-600'
              }`}
            >
              📱 Garçom
            </button>
            <button
              onClick={() => setView('manager')}
              className={`px-3 py-1 rounded text-sm font-medium ${
                view === 'manager' ? 'bg-amber-500 text-white' : 'text-gray-600'
              }`}
            >
              💻 Gerente
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      {view === 'waiter' ? (
        <WaiterInterface onOrderCreated={() => setOrderUpdateTrigger(prev => prev + 1)} />
      ) : (
        <ManagerInterface key={orderUpdateTrigger} />
      )}
    </div>
  );
};

export default App;
