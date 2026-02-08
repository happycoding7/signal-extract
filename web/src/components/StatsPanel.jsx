import { useState, useEffect } from 'react';
import { fetchStats } from '../api';

const SOURCE_LABELS = {
  github_issue: 'GitHub Issues',
  github_release: 'GitHub Releases',
  github_discussion: 'GitHub Discussions',
  hacker_news: 'Hacker News',
  rss: 'RSS',
  nvd_cve: 'NVD/CVE',
};

export default function StatsPanel() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStats()
      .then((data) => {
        setStats(data);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="stats-panel error">Stats: {error}</div>;
  if (!stats) return <div className="stats-panel loading">Loading stats...</div>;

  const formatDate = (iso) => {
    if (!iso) return 'Never';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="stats-panel">
      <h3>Statistics</h3>
      <div className="stat-row">
        <span className="stat-label">Total items</span>
        <span className="stat-value">{stats.total_items}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Total digests</span>
        <span className="stat-value">{stats.total_digests}</span>
      </div>
      <div className="stat-row">
        <span className="stat-label">Last collected</span>
        <span className="stat-value">{formatDate(stats.latest_collection)}</span>
      </div>

      {stats.by_source && Object.keys(stats.by_source).length > 0 && (
        <div className="stat-section">
          <h4>By Source</h4>
          {Object.entries(stats.by_source).map(([source, count]) => (
            <div key={source} className="stat-row">
              <span className="stat-label">{SOURCE_LABELS[source] || source}</span>
              <span className="stat-value">{count}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
