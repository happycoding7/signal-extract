const SOURCES = [
  { value: '', label: 'All sources' },
  { value: 'github_issue', label: 'GitHub Issues' },
  { value: 'github_release', label: 'GitHub Releases' },
  { value: 'github_discussion', label: 'GitHub Discussions' },
  { value: 'hacker_news', label: 'Hacker News' },
  { value: 'rss', label: 'RSS' },
  { value: 'nvd_cve', label: 'NVD/CVE' },
];

export default function Filters({ filters, onChange }) {
  return (
    <div className="filters">
      <div className="filter-group">
        <label>Source</label>
        <select
          value={filters.source}
          onChange={(e) => onChange({ source: e.target.value })}
          className="filter-select"
        >
          {SOURCES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-group">
        <label>Min Score</label>
        <input
          type="number"
          min="0"
          max="100"
          value={filters.minScore}
          onChange={(e) => onChange({ minScore: parseInt(e.target.value) || 0 })}
          className="filter-input"
        />
      </div>

      <div className="filter-group">
        <label>Since</label>
        <input
          type="date"
          value={filters.since}
          onChange={(e) => onChange({ since: e.target.value })}
          className="filter-input"
        />
      </div>
    </div>
  );
}
