import { useState, useEffect } from 'react';
import { fetchOpportunities, fetchOpportunityTrends } from '../api';

const BUYER_OPTIONS = [
  { value: '', label: 'All buyers' },
  { value: 'devops', label: 'DevOps Lead' },
  { value: 'ciso', label: 'CISO' },
  { value: 'vp eng', label: 'VP Engineering' },
  { value: 'platform', label: 'Platform Team' },
  { value: 'cto', label: 'CTO' },
];

const MARKET_OPTIONS = [
  { value: '', label: 'All markets' },
  { value: 'boring', label: 'Boring/Growing' },
  { value: 'hype', label: 'Hype/Crowded' },
];

const EFFORT_COLORS = {
  weekend: '#4ec9b0',
  '1-2 weeks': '#dcdcaa',
  'month+': '#d16969',
};

function ConfidenceBadge({ confidence }) {
  let color = '#6a6a6a';
  if (confidence >= 80) color = '#4ec9b0';
  else if (confidence >= 50) color = '#dcdcaa';
  else color = '#d16969';
  return (
    <span className="confidence-badge" style={{ backgroundColor: color }}>
      {confidence}
    </span>
  );
}

function EffortBadge({ effort }) {
  return (
    <span
      className="effort-badge"
      style={{ backgroundColor: EFFORT_COLORS[effort] || '#6a6a6a' }}
    >
      {effort}
    </span>
  );
}

function TrendIndicator({ trends, opportunityId }) {
  if (!trends) return null;
  const trend = trends.find((t) => t.id === opportunityId);
  if (!trend || trend.data_points.length < 2) return null;

  const points = trend.data_points;
  const latest = points[points.length - 1].confidence;
  const previous = points[points.length - 2].confidence;
  const diff = latest - previous;

  if (diff > 0) return <span className="trend-up" title={`+${diff} from previous`}>+{diff}</span>;
  if (diff < 0) return <span className="trend-down" title={`${diff} from previous`}>{diff}</span>;
  return <span className="trend-flat" title="No change">=</span>;
}

export default function OpportunitiesView({ onSelectOpportunity }) {
  const [opportunities, setOpportunities] = useState([]);
  const [trends, setTrends] = useState(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    minConfidence: 0,
    buyer: '',
    marketType: '',
    since: '',
    limit: 50,
    offset: 0,
  });

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchOpportunities(filters),
      fetchOpportunityTrends(),
    ])
      .then(([oppData, trendData]) => {
        setOpportunities(oppData.opportunities || []);
        setTotal(oppData.total || 0);
        setTrends(trendData.trends || []);
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

  const currentPage = Math.floor(filters.offset / filters.limit) + 1;
  const totalPages = Math.ceil(total / filters.limit);

  return (
    <div className="opportunities-view">
      {/* Filters */}
      <div className="filters">
        <div className="filter-group">
          <label>Min Confidence</label>
          <input
            type="number"
            min="0"
            max="100"
            value={filters.minConfidence}
            onChange={(e) => handleFilterChange({ minConfidence: parseInt(e.target.value) || 0 })}
            className="filter-input"
          />
        </div>
        <div className="filter-group">
          <label>Buyer</label>
          <select
            value={filters.buyer}
            onChange={(e) => handleFilterChange({ buyer: e.target.value })}
            className="filter-select"
          >
            {BUYER_OPTIONS.map((b) => (
              <option key={b.value} value={b.value}>{b.label}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Market</label>
          <select
            value={filters.marketType}
            onChange={(e) => handleFilterChange({ marketType: e.target.value })}
            className="filter-select"
          >
            {MARKET_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Since</label>
          <input
            type="date"
            value={filters.since}
            onChange={(e) => handleFilterChange({ since: e.target.value })}
            className="filter-input"
          />
        </div>
      </div>

      {loading && <div className="loading">Loading opportunities...</div>}
      {error && <div className="error">{error}</div>}

      {/* Opportunity cards */}
      <div className="opportunity-cards">
        {opportunities.map((opp) => (
          <div
            key={`${opp.id}-${opp.run_id}`}
            className="opportunity-card"
            onClick={() => onSelectOpportunity && onSelectOpportunity(opp.id)}
          >
            <div className="opp-card-header">
              <div className="opp-card-title-row">
                <ConfidenceBadge confidence={opp.confidence} />
                <h3 className="opp-card-title">{opp.title}</h3>
                <TrendIndicator trends={trends} opportunityId={opp.id} />
              </div>
              <div className="opp-card-meta">
                <EffortBadge effort={opp.effort_estimate} />
                <span className="opp-buyer-badge">{opp.target_buyer}</span>
                <span className="opp-market-badge">{opp.market_type}</span>
              </div>
            </div>
            <div className="opp-card-body">
              <p className="opp-pain">{opp.pain}</p>
              <p className="opp-solution">{opp.solution_shape}</p>
            </div>
            <div className="opp-card-footer">
              <span className="opp-evidence-count">
                {opp.evidence.length} evidence source{opp.evidence.length !== 1 ? 's' : ''}
              </span>
              <span className="opp-date">
                {new Date(opp.generated_at).toLocaleDateString('en-US', {
                  month: 'short', day: 'numeric',
                })}
              </span>
            </div>
          </div>
        ))}
      </div>

      {!loading && opportunities.length === 0 && (
        <div className="empty">
          No opportunities found. Run 'python main.py opportunities-json' to generate structured opportunities.
        </div>
      )}

      {total > 0 && (
        <div className="pagination">
          <button
            onClick={() => handlePageChange(-1)}
            disabled={filters.offset === 0}
          >
            Previous
          </button>
          <span>
            Page {currentPage} of {totalPages} ({total} opportunities)
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
