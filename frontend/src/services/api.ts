const API_BASE_URL = `http://${window.location.hostname}:8000/api/v1`;

export const fetchWithAuth = async (endpoint: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('token');
  const headers = new Headers(options.headers || {});
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Handle unauthorized (e.g., redirect to login or clear token)
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Request failed with status ${response.status}`);
  }

  return response.json();
};

export const inventoryApi = {
  getInventory: () => fetchWithAuth('/inventory'),
  requestItem: (itemId: number, destination: string) => 
    fetchWithAuth('/deliveries', {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId, destination }),
    }),
  createItem: (item: any) => 
    fetchWithAuth('/inventory', {
      method: 'POST',
      body: JSON.stringify(item),
    }),
  updateItem: (itemId: number, item: any) => 
    fetchWithAuth(`/inventory/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(item),
    }),
  deleteItem: (itemId: number) => 
    fetchWithAuth(`/inventory/${itemId}`, {
      method: 'DELETE',
    }),
};

export const rackApi = {
  unlockRack: (rackId: number) => fetchWithAuth(`/racks/${rackId}/unlock`, { method: 'PUT' }),
  lockRack: (rackId: number) => fetchWithAuth(`/racks/${rackId}/lock`, { method: 'PUT' }),
  verifyAccess: (rackId: number, password: string) => fetchWithAuth(`/racks/${rackId}/verify`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  }),
  logTransaction: (rackId: number, itemId: number, action: 'add' | 'remove', quantity: number) => fetchWithAuth(`/racks/${rackId}/transaction`, {
    method: 'POST',
    body: JSON.stringify({ item_id: itemId, action, quantity }),
  }),
};

export const configApi = {
  getConfig: () => fetchWithAuth('/config'),
  updateConfig: (config: any) => fetchWithAuth('/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  }),
};

export const deliveriesApi = {
  getDeliveries: () => fetchWithAuth('/deliveries'),
  updateDeliveryStatus: (deliveryId: number, status: string) => fetchWithAuth(`/deliveries/${deliveryId}`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  }),
  requestQuickItem: (payload: { username: string, pc_no: string, item_id: number, location: string, rack_id?: number | null }) => fetchWithAuth('/quick-delivery', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  getQuickDeliveries: (username: string) => fetchWithAuth(`/quick-deliveries?username=${encodeURIComponent(username)}`),
};

export const usersApi = {
  getUsers: () => fetchWithAuth('/users'),
};
