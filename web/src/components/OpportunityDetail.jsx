import { useState, useEffect } from 'react';
import { fetchOpportunity, fetchOpportunityTrends } from '../api';

const EFFORT_COLORS = {
  weekend: '#4ec9b0',
  '1-2 weeks': '#dcdcaa',
  'month+': '#d16969',
};

const SOURCE_COLORS = {
  github_issue: '#c586c0',
  github_release: '#4ec9b0',
  github_discussion: '#569cd6',
  hacker_news: '#ff6600',
  rss: '#608b4e',
  nvd_cve: '#d16969',
};

export default function OpportunityDetail({ opportunityId, onBack }) {
  const [opp, setOpp] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!opportunityId) return;
    setLoading(true);
    Promise.all([
      fetchOpportunity(opportunityId),
      fetchOpportunityTrends(),
    ])
      .then(([oppData, trendData]) => {
        setOpp(oppData);
        const trends = trendData.trends || [];
        setTrend(trends.find((t) => t.id === opportunityId) || null);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [opportunityId]);

  if (!opportunityId) {
    return (
      <div className="opp-detail empty-state">
        <p>Select an opportunity to view details.</p>
      </div>
    );
  }

  if (loading) return <div className="opp-detail loading">Loading...</div>;
  if (error) return <div className="opp-detail error">{error}</div>;
  if (!opp) return null;

  const formatDate = (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  return (
    <div className="opp-detail">
      {onBack && (
        <button className="opp-back-btn" onClick={onBack}>
          Back to list
        </button>
      )}

      <div className="opp-detail-header">
        <div className="opp-detail-title-row">
          <span
            className="confidence-badge confidence-large"
            style={{
              backgroundColor:
                opp.confidence >= 80 ? '#4ec9b0' :
                opp.confidence >= 50 ? '#dcdcaa' : '#d16969',
            }}
          >
            {opp.confidence}
          </span>
          <h2>{opp.title}</h2>
        </div>
        <div className="opp-detail-meta">
          <span
            className="effort-badge"
            style={{ backgroundColor: EFFORT_COLORS[opp.effort_estimate] || '#6a6a6a' }}
          >
            {opp.effort_estimate}
          </span>
          <span className="opp-buyer-badge">{opp.target_buyer}</span>
          <span className="opp-market-badge">{opp.market_type}</span>
          <span className="opp-detail-date">{formatDate(opp.generated_at)}</span>
        </div>
      </div>

      {/* Trend history */}
      {trend && trend.data_points.length > 1 && (
        <div className="opp-section">
          <h3>Confidence History</h3>
          <div className="trend-history">
            {trend.data_points.map((dp, i) => (
              <div key={dp.run_id} className="trend-point">
                <span className="trend-date">
                  {new Date(dp.generated_at).toLocaleDateString('en-US', {
                    month: 'short', day: 'numeric',
                  })}
                </span>
                <span
                  className="trend-bar"
                  style={{ width: `${dp.confidence}%` }}
                >
                  {dp.confidence}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="opp-section">
        <h3>Pain</h3>
        <p>{opp.pain}</p>
      </div>

      <div className="opp-section">
        <h3>Solution Shape</h3>
        <p>{opp.solution_shape}</p>
      </div>

      <div className="opp-section">
        <h3>Monetization</h3>
        <p>{opp.monetization}</p>
      </div>

      <div className="opp-section">
        <h3>Moat</h3>
        <p>{opp.moat}</p>
      </div>

      <div className="opp-section">
        <h3>Competition</h3>
        <p>{opp.competition_notes}</p>
      </div>

      {/* Evidence */}
      <div className="opp-section">
        <h3>Evidence ({opp.evidence.length})</h3>
        <div className="evidence-list">
          {opp.evidence.map((ev, i) => (
            <div key={i} className="evidence-item">
              <span
                className="source-badge"
                style={{ backgroundColor: SOURCE_COLORS[ev.source] || '#888' }}
              >
                {ev.source.replace(/_/g, ' ')}
              </span>
              <a
                href={ev.url}
                target="_blank"
                rel="noopener noreferrer"
                className="evidence-link"
              >
                {ev.item_title}
              </a>
              <span className="evidence-score">score: {ev.score}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
