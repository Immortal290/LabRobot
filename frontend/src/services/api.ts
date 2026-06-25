const API_BASE_URL = '/api/v1';

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
  getRacks: () => fetchWithAuth('/racks'),
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
  getNetworkIp: () => fetchWithAuth('/network/ip'),
  getTunnelUrl: () => fetchWithAuth('/network/tunnel'),
};

export const deliveriesApi = {
  getDeliveries: () => fetchWithAuth('/deliveries'),
  getDeliveryById: (deliveryId: number) => fetchWithAuth(`/deliveries/${deliveryId}`),
  updateDeliveryStatus: (deliveryId: number, status: string) => fetchWithAuth(`/deliveries/${deliveryId}`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  }),
  requestQuickItem: (payload: { username: string, pc_no: string, item_id: number, location: string, rack_id?: number | null, phone_number?: string | null }) => fetchWithAuth('/quick-delivery', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  getQuickDeliveries: (username: string) => fetchWithAuth(`/quick-deliveries?username=${encodeURIComponent(username)}`),
  cancelDelivery: (deliveryId: number) => fetchWithAuth(`/deliveries/${deliveryId}/cancel`, {
    method: 'DELETE',
  }),
  confirmPickup: (deliveryId: number) => fetchWithAuth(`/deliveries/${deliveryId}/confirm-pickup`, {
    method: 'POST',
  }),
  /** Verify the 4-digit OTP code to unlock the locker compartment. */
  verifyDeliveryOTP: (deliveryId: number, otp: string) => fetchWithAuth(`/deliveries/${deliveryId}/verify-otp`, {
    method: 'POST',
    body: JSON.stringify({ otp }),
  }),
};

export const robotApi = {
  sendCommand: (action: string, panelId?: number) => fetchWithAuth('/robot/command', {
    method: 'POST',
    body: JSON.stringify({ action, panel_id: panelId ?? null }),
  }),
  returnToBase: () => fetchWithAuth('/robot/command', {
    method: 'POST',
    body: JSON.stringify({ action: 'return_to_base' }),
  }),
  unlockPanel: (panelId: number) => fetchWithAuth('/robot/command', {
    method: 'POST',
    body: JSON.stringify({ action: 'unlock_panel', panel_id: panelId }),
  }),
  emergencyStop: () => fetchWithAuth('/robot/command', {
    method: 'POST',
    body: JSON.stringify({ action: 'emergency_stop' }),
  }),
};

export const usersApi = {
  getUsers: () => fetchWithAuth('/users'),
  updateUser: (id: number, data: any) => fetchWithAuth(`/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  deleteUser: (id: number) => fetchWithAuth(`/users/${id}`, {
    method: 'DELETE',
  })
};


/** Robot control commands sent via WebSocket to the bridge. */
export const robotCommands = {
  /**
   * Sends a command via an open WebSocket connection.
   * Pass the WebSocket ref from the calling component.
   */
  send: (ws: WebSocket | null, action: string, param?: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'command', action, param }));
      return true;
    }
    return false;
  },
  returnToBase:   (ws: WebSocket | null) => robotCommands.send(ws, 'return_to_base'),
  eStop:          (ws: WebSocket | null, active: boolean) => robotCommands.send(ws, 'estop', active),
  unlockPanel:    (ws: WebSocket | null, rackId: number) => robotCommands.send(ws, 'unlock_panel', rackId),
  cancelTask:     (ws: WebSocket | null) => robotCommands.send(ws, 'cancel_task'),
  forceComplete:  (ws: WebSocket | null) => robotCommands.send(ws, 'force_complete'),
};

/** Barcode location management — admin only for create/update/delete. */
export const barcodeApi = {
  list:   () => fetchWithAuth('/barcodes'),
  lookup: (value: string) => fetchWithAuth(`/barcodes/lookup?value=${encodeURIComponent(value)}`),
  create: (data: any) => fetchWithAuth('/barcodes', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  update: (id: number, data: any) => fetchWithAuth(`/barcodes/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  }),
  delete: (id: number) => fetchWithAuth(`/barcodes/${id}`, { method: 'DELETE' }),
};

/** Robot telemetry history — read-only, admin only. */
export const robotHistoryApi = {
  getHistory:  (limit = 100) => fetchWithAuth(`/robot/history?limit=${limit}`),
  saveSnapshot: (data: any) => fetchWithAuth('/robot/snapshot', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

/** Navigation log — admin only. */
export const navLogApi = {
  list:   (limit = 50) => fetchWithAuth(`/navigation-logs?limit=${limit}`),
  create: (data: any)  => fetchWithAuth('/navigation-logs', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};

/** OTP audit log — admin only. */
export const otpLogApi = {
  list: (limit = 50) => fetchWithAuth(`/otp-logs?limit=${limit}`),
};
