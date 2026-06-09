import React, { useState, useEffect } from 'react';
import { GlassPanel } from '../components/GlassPanel';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Package, LockOpen, LogOut, RefreshCcw, Box, ShieldAlert, Plus, Minus } from 'lucide-react';
import { inventoryApi, rackApi } from '../services/api';

export const UserDashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('rack');
  const [inventory, setInventory] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  
  // Rack Access State
  const [selectedRack, setSelectedRack] = useState<number | null>(null);
  const [authPassword, setAuthPassword] = useState('');
  const [isRackUnlocked, setIsRackUnlocked] = useState(false);
  const [transactionQuantity, setTransactionQuantity] = useState(1);
  const [selectedItem, setSelectedItem] = useState<number | null>(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const loadInventory = async () => {
    try {
      setLoading(true);
      const data = await inventoryApi.getInventory();
      setInventory(data);
      if (data.length > 0 && !selectedItem) {
        setSelectedItem(data[0].id);
      }
    } catch (err) {
      console.error(err);
      setMessage("Failed to load inventory");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'inventory' || activeTab === 'rack') {
      loadInventory();
    }
  }, [activeTab]);

  const handleRequestItem = async (itemId: number) => {
    try {
      setMessage("Requesting delivery...");
      await inventoryApi.requestItem(itemId, "Lab Desk");
      setMessage("Item requested successfully! Robot is on its way.");
      loadInventory();
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage("Failed to request item");
      setTimeout(() => setMessage(''), 3000);
    }
  };

  const handleVerifyRack = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRack) return;
    try {
      setMessage(`Verifying access for Rack ${selectedRack}...`);
      await rackApi.verifyAccess(selectedRack, authPassword);
      await rackApi.unlockRack(selectedRack);
      setIsRackUnlocked(true);
      setMessage(`Rack ${selectedRack} unlocked successfully!`);
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(`Authentication failed. Incorrect password.`);
      setTimeout(() => setMessage(''), 3000);
    }
  };

  const handleLogTransaction = async (action: 'add' | 'remove') => {
    if (!selectedRack || !selectedItem) return;
    try {
      setMessage(`Processing ${action}...`);
      await rackApi.logTransaction(selectedRack, selectedItem, action, transactionQuantity);
      setMessage(`Successfully logged ${action} of ${transactionQuantity} item(s)`);
      loadInventory();
      setTransactionQuantity(1);
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(`Failed: ${(err as Error).message}`);
      setTimeout(() => setMessage(''), 3000);
    }
  };

  const handleCloseRack = async () => {
    if (selectedRack) {
      await rackApi.lockRack(selectedRack);
    }
    setSelectedRack(null);
    setIsRackUnlocked(false);
    setAuthPassword('');
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2>Welcome, {user?.username}</h2>
          <span style={{ color: 'var(--text-secondary)' }}>LabRobot Secure Access Terminal</span>
        </div>
        <button onClick={handleLogout} className="btn" style={{ background: 'transparent', color: 'var(--text-secondary)' }}>
          <LogOut size={20} />
        </button>
      </header>

      <div style={{ display: 'flex', gap: '16px', marginBottom: '2rem' }}>
        <button 
          className={`btn ${activeTab === 'rack' ? 'btn-primary' : ''}`}
          style={{ background: activeTab === 'rack' ? '' : 'rgba(255,255,255,0.05)' }}
          onClick={() => { setActiveTab('rack'); handleCloseRack(); }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <LockOpen size={18} /> Access Racks
          </div>
        </button>
        <button 
          className={`btn ${activeTab === 'inventory' ? 'btn-primary' : ''}`}
          style={{ background: activeTab === 'inventory' ? '' : 'rgba(255,255,255,0.05)' }}
          onClick={() => setActiveTab('inventory')}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Package size={18} /> Catalog
          </div>
        </button>
      </div>
      
      {message && (
        <div style={{ padding: '16px', marginBottom: '16px', background: 'rgba(59, 130, 246, 0.2)', borderLeft: '4px solid var(--accent-blue)', borderRadius: '4px', animation: 'fade-in 0.3s ease-out' }}>
          {message}
        </div>
      )}

      {activeTab === 'rack' && !selectedRack && (
        <div>
          <h3 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>Select a Rack to Access</h3>
          <div className="grid-cols-2" style={{ gap: '24px', maxWidth: '600px', margin: '0 auto' }}>
            {[1, 2, 3, 4].map(rackId => (
              <GlassPanel 
                key={rackId} 
                className="hover-scale"
                style={{ cursor: 'pointer', textAlign: 'center', padding: '40px 20px' }}
                // @ts-ignore
                onClick={() => setSelectedRack(rackId)}
              >
                <Box size={48} color="var(--accent-cyan)" style={{ margin: '0 auto 1rem' }} />
                <h3>Rack {rackId}</h3>
                <span style={{ color: 'var(--text-secondary)' }}>Tap to unlock</span>
              </GlassPanel>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'rack' && selectedRack && !isRackUnlocked && (
        <GlassPanel style={{ maxWidth: '500px', margin: '0 auto', textAlign: 'center' }}>
          <ShieldAlert size={48} color="var(--accent-red)" style={{ margin: '0 auto 1rem' }} />
          <h2 style={{ marginBottom: '1rem' }}>Authenticate for Rack {selectedRack}</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
            Individual authentication is required to unlock this specific rack. Please verify your identity.
          </p>
          <form onSubmit={handleVerifyRack} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <input 
              type="password" 
              className="input-field" 
              placeholder="Enter your secure password" 
              value={authPassword}
              onChange={e => setAuthPassword(e.target.value)}
              required
            />
            <div style={{ display: 'flex', gap: '16px' }}>
              <button type="button" onClick={handleCloseRack} className="btn" style={{ flex: 1, background: 'rgba(255,255,255,0.1)' }}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>
                Unlock
              </button>
            </div>
          </form>
        </GlassPanel>
      )}

      {activeTab === 'rack' && selectedRack && isRackUnlocked && (
        <GlassPanel style={{ maxWidth: '800px', margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <LockOpen size={28} color="var(--accent-green)" />
              <h2 style={{ margin: 0 }}>Rack {selectedRack} Unlocked</h2>
            </div>
            <button onClick={handleCloseRack} className="btn" style={{ background: 'var(--accent-red)', color: '#fff' }}>
              Lock Rack & Finish
            </button>
          </div>

          <h3 style={{ marginBottom: '1rem' }}>Log Activity</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
            Select the item you are interacting with and log whether you are adding it to or removing it from the rack.
          </p>

          <div style={{ display: 'flex', gap: '16px', marginBottom: '2rem', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 300px' }}>
              <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)' }}>Item</label>
              <select 
                className="input-field" 
                value={selectedItem || ''} 
                onChange={(e) => setSelectedItem(Number(e.target.value))}
              >
                {inventory.map(item => (
                  <option key={item.id} value={item.id}>{item.name} (Available: {item.quantity})</option>
                ))}
              </select>
            </div>
            
            <div style={{ flex: '0 0 150px' }}>
              <label style={{ display: 'block', marginBottom: '8px', color: 'var(--text-secondary)' }}>Quantity</label>
              <input 
                type="number" 
                className="input-field" 
                min="1" 
                value={transactionQuantity} 
                onChange={e => setTransactionQuantity(Number(e.target.value))} 
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '16px' }}>
            <button onClick={() => handleLogTransaction('add')} className="btn" style={{ flex: 1, background: 'rgba(16, 185, 129, 0.2)', color: 'var(--accent-green)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <Plus size={20} /> Add to Rack
            </button>
            <button onClick={() => handleLogTransaction('remove')} className="btn" style={{ flex: 1, background: 'rgba(239, 68, 68, 0.2)', color: 'var(--accent-red)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <Minus size={20} /> Remove from Rack
            </button>
          </div>
        </GlassPanel>
      )}

      {activeTab === 'inventory' && (
        <div className="grid-cols-2">
          {loading ? (
             <div className="flex-center" style={{ gridColumn: 'span 2', padding: '2rem' }}>
                <RefreshCcw className="spinner" size={24} /> Loading inventory...
             </div>
          ) : inventory.length === 0 ? (
             <div style={{ gridColumn: 'span 2', textAlign: 'center', color: 'var(--text-secondary)' }}>No items in inventory.</div>
          ) : inventory.map(item => (
            <GlassPanel key={item.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ marginBottom: '4px' }}>{item.name}</h3>
                <span style={{ fontSize: '0.9rem', color: item.available ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                  {item.quantity} Available
                </span>
              </div>
              <button 
                onClick={() => handleRequestItem(item.id)}
                className="btn btn-primary" 
                disabled={!item.available || item.quantity <= 0}
                style={{ opacity: (!item.available || item.quantity <= 0) ? 0.5 : 1 }}
              >
                Request Delivery
              </button>
            </GlassPanel>
          ))}
        </div>
      )}

    </div>
  );
};
