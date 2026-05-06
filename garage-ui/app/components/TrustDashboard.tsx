// garage-ui/app/components/TrustDashboard.tsx
import React, { useEffect, useState } from 'react';

interface QuarantineItem {
  id: number;
  candidate_data: string;
  source_message: string;
  confidence_score: number;
  item_type: string;
  status: string;
  created_at: string;
}

export default function TrustDashboard() {
  const [items, setItems] = useState<QuarantineItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchItems = async () => {
    try {
      const res = await fetch(`http://${window.location.hostname}:5001/api/quarantine`);
      if (res.ok) setItems(await res.json());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, []);

  const handleUpdate = async (id: number, status: string) => {
    try {
      await fetch(`http://${window.location.hostname}:5001/api/quarantine/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      });
      fetchItems();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="p-6 h-full overflow-y-auto bg-[var(--panel-bg)]">
      <h2 className="text-xl font-bold mb-2">Trust & Autonomy Dashboard</h2>
      <p className="text-[var(--dim-text)] text-sm mb-6">Review quarantined memory and blocked autonomous actions.</p>
      
      {loading ? <p>Loading...</p> : items.length === 0 ? <p>Queue is empty.</p> : (
        <div className="space-y-4">
          {items.map(item => (
            <div key={item.id} className="border border-[var(--border-color)] rounded-lg p-4 bg-black/20">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-bold px-2 py-1 rounded bg-[var(--accent-color)] text-white">
                  {item.item_type.toUpperCase()}
                </span>
                <span className="text-sm font-mono text-yellow-500">
                  Confidence: {item.confidence_score}
                </span>
              </div>
              <p className="font-medium mb-1">{item.candidate_data}</p>
              <p className="text-xs text-[var(--dim-text)] mb-4 font-mono whitespace-pre-wrap">Source: {item.source_message}</p>
              <div className="flex gap-2">
                <button onClick={() => handleUpdate(item.id, 'approved')} className="px-3 py-1 bg-green-600/80 text-white rounded text-sm hover:bg-green-600">Approve</button>
                <button onClick={() => handleUpdate(item.id, 'rejected')} className="px-3 py-1 bg-red-600/80 text-white rounded text-sm hover:bg-red-600">Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
