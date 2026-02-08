import { useState, useEffect } from 'react';
import { fetchDigest } from '../api';

const TYPE_LABELS = {
  daily: 'DAILY ENTERPRISE OPPORTUNITY SCAN',
  weekly: 'WEEKLY ENTERPRISE DEV-TOOL SYNTHESIS',
  opportunities: 'ENTERPRISE OPPORTUNITY REPORT',
};

export default function DigestDetail({ digestId }) {
  const [digest, setDigest] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!digestId) return;
    setLoading(true);
    fetchDigest(digestId)
      .then((data) => {
        setDigest(data);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [digestId]);

  if (!digestId) {
    return (
      <div className="digest-detail empty-state">
        <p>Select a run from the sidebar to view its results.</p>
      </div>
    );
  }

  if (loading) return <div className="digest-detail loading">Loading...</div>;
  if (error) return <div className="digest-detail error">{error}</div>;
  if (!digest) return null;

  const formatDate = (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="digest-detail">
      <div className="digest-detail-header">
        <h2>{TYPE_LABELS[digest.digest_type] || digest.digest_type.toUpperCase()}</h2>
        <div className="digest-meta">
          <span>{formatDate(digest.generated_at)}</span>
          <span className="separator">|</span>
          <span>{digest.item_count} items analyzed</span>
        </div>
      </div>
      <pre className="digest-content">{digest.content}</pre>
    </div>
  );
}
