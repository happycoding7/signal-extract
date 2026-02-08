import { useState } from 'react';
import DigestList from './components/DigestList';
import DigestDetail from './components/DigestDetail';
import ItemsTable from './components/ItemsTable';
import OpportunitiesView from './components/OpportunitiesView';
import OpportunityDetail from './components/OpportunityDetail';
import StatsPanel from './components/StatsPanel';
import './App.css';

function App() {
  const [view, setView] = useState('digests');
  const [selectedDigest, setSelectedDigest] = useState(null);
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);

  const handleSelectOpportunity = (id) => {
    setSelectedOpportunity(id);
  };

  const handleBackToOpportunities = () => {
    setSelectedOpportunity(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>signal-extract</h1>
        <span className="app-subtitle">Enterprise Dev-Tool Opportunity Discovery</span>
        <nav className="app-nav">
          <button
            className={view === 'digests' ? 'active' : ''}
            onClick={() => setView('digests')}
          >
            Digests
          </button>
          <button
            className={view === 'items' ? 'active' : ''}
            onClick={() => setView('items')}
          >
            Items
          </button>
          <button
            className={view === 'opportunities' ? 'active' : ''}
            onClick={() => { setView('opportunities'); setSelectedOpportunity(null); }}
          >
            Opportunities
          </button>
        </nav>
      </header>

      <div className="layout">
        <aside className="sidebar">
          {view === 'digests' && (
            <DigestList onSelect={setSelectedDigest} selected={selectedDigest} />
          )}
          <StatsPanel />
        </aside>
        <main className="main-content">
          {view === 'digests' && <DigestDetail digestId={selectedDigest} />}
          {view === 'items' && <ItemsTable />}
          {view === 'opportunities' && !selectedOpportunity && (
            <OpportunitiesView onSelectOpportunity={handleSelectOpportunity} />
          )}
          {view === 'opportunities' && selectedOpportunity && (
            <OpportunityDetail
              opportunityId={selectedOpportunity}
              onBack={handleBackToOpportunities}
            />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
