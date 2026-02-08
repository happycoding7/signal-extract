import { useState, useEffect } from 'react';
import { fetchDigests } from '../api';

const TYPE_LABELS = {
  daily: 'Daily',
  weekly: 'Weekly',
  opportunities: 'Opportunities',
};

const TYPE_COLORS = {
  daily: '#4ec9b0',
  weekly: '#569cd6',
  opportunities: '#dcdcaa',
};

export default function DigestList({ onSelect, selected }) {
  const [digests, setDigests] = useState([]);
  const [filterType, setFilterType] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetchDigests(filterType || null)
      .then((data) => {
        setDigests(data.digests || []);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filterType]);

  const formatDate = (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="digest-list">
      <div className="digest-list-header">
        <h3>Run History</h3>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="filter-select"
        >
          <option value="">All types</option>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="opportunities">Opportunities</option>
        </select>
      </div>

      {loading && <div className="loading">Loading...</div>}
      {error && <div className="error">{error}</div>}

      <div className="digest-entries">
        {digests.map((d) => (
          <div
            key={d.id}
            className={`digest-entry ${selected === d.id ? 'selected' : ''}`}
            onClick={() => onSelect(d.id)}
          >
            <span
              className="digest-type-badge"
              style={{ backgroundColor: TYPE_COLORS[d.digest_type] || '#888' }}
            >
              {TYPE_LABELS[d.digest_type] || d.digest_type}
            </span>
            <span className="digest-date">{formatDate(d.generated_at)}</span>
            <span className="digest-count">{d.item_count} items</span>
          </div>
        ))}
        {!loading && digests.length === 0 && (
          <div className="empty">No digests found. Run 'python main.py digest' first.</div>
        )}
      </div>
    </div>
  );
}
