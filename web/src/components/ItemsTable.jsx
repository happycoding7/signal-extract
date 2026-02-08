import { useState, useEffect } from 'react';
import { fetchItems } from '../api';
import Filters from './Filters';

const SOURCE_COLORS = {
  github_issue: '#c586c0',
  github_release: '#4ec9b0',
  github_discussion: '#569cd6',
  hacker_news: '#ff6600',
  rss: '#608b4e',
  nvd_cve: '#d16969',
};

function ScoreBadge({ score }) {
  let color = '#6a6a6a';
  if (score > 70) color = '#4ec9b0';
  else if (score > 50) color = '#dcdcaa';
  return (
    <span className="score-badge" style={{ backgroundColor: color }}>
      {score}
    </span>
  );
}

function SourceBadge({ source }) {
  const label = source.replace(/_/g, ' ');
  return (
    <span
      className="source-badge"
      style={{ backgroundColor: SOURCE_COLORS[source] || '#888' }}
    >
      {label}
    </span>
  );
}

export default function ItemsTable() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedHash, setExpandedHash] = useState(null);
  const [filters, setFilters] = useState({
    source: '',
    minScore: 40,
    since: '',
    limit: 50,
    offset: 0,
  });

  useEffect(() => {
    setLoading(true);
    fetchItems(filters)
      .then((data) => {
        setItems(data.items || []);
        setTotal(data.total || 0);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filters]);

  const handleFilterChange = (newFilters) => {
    setFilters((prev) => ({ ...prev, ...newFilters, offset: 0 }));
  };

  const handlePageChange = (direction) => {
    setFilters((prev) => ({
      ...prev,
      offset: Math.max(0, prev.offset + direction * prev.limit),
    }));
  };

  const formatDate = (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const currentPage = Math.floor(filters.offset / filters.limit) + 1;
  const totalPages = Math.ceil(total / filters.limit);

  return (
    <div className="items-view">
      <Filters filters={filters} onChange={handleFilterChange} />

      {loading && <div className="loading">Loading...</div>}
      {error && <div className="error">{error}</div>}

      <div className="items-table-container">
        <table className="items-table">
          <thead>
            <tr>
              <th className="col-score">Score</th>
              <th className="col-source">Source</th>
              <th className="col-title">Title</th>
              <th className="col-date">Date</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <>
                <tr
                  key={item.content_hash}
                  className={`item-row ${expandedHash === item.content_hash ? 'expanded' : ''}`}
                  onClick={() =>
                    setExpandedHash(
                      expandedHash === item.content_hash ? null : item.content_hash
                    )
                  }
                >
                  <td className="col-score">
                    <ScoreBadge score={item.score} />
                  </td>
                  <td className="col-source">
                    <SourceBadge source={item.source} />
                  </td>
                  <td className="col-title">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {item.title}
                    </a>
                  </td>
                  <td className="col-date">{formatDate(item.collected_at)}</td>
                </tr>
                {expandedHash === item.content_hash && (
                  <tr key={`${item.content_hash}-body`} className="item-body-row">
                    <td colSpan="4">
                      <div className="item-body">{item.body}</div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>

        {!loading && items.length === 0 && (
          <div className="empty">No items found. Try adjusting filters or run 'python main.py collect'.</div>
        )}
      </div>

      {total > 0 && (
        <div className="pagination">
          <button
            onClick={() => handlePageChange(-1)}
            disabled={filters.offset === 0}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages} ({total} items)
          </span>
          <button
            onClick={() => handlePageChange(1)}
            disabled={filters.offset + filters.limit >= total}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
