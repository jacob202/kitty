import { useState } from 'react';

interface OnboardingWizardProps {
  onComplete?: (domains: string[], sources?: string[]) => void;
  onSkip?: () => void;
}

// Available domains for selection
const AVAILABLE_DOMAINS = [
  { id: 'audio', label: 'Audio & Music', icon: '🎵', description: 'Speakers, amplifiers, headphones, vinyl' },
  { id: 'automotive', label: 'Automotive', icon: '🚗', description: 'Cars, motorcycles, restorations' },
  { id: 'fitness', label: 'Fitness', icon: '💪', description: 'Workouts, sports, training' },
  { id: 'health', label: 'Health', icon: '❤️', description: 'Nutrition, sleep, wellness' },
  { id: 'growth', label: 'Growth', icon: '📈', description: 'Career, investments, skills' },
  { id: 'code', label: 'Coding', icon: '💻', description: 'Projects, languages, tools' },
  { id: 'design', label: 'Design', icon: '🎨', description: 'UI/UX, graphics, photography' },
  { id: 'creative', label: 'Creative', icon: '🎬', description: 'Writing, art, music production' },
  { id: 'research', label: 'Research', icon: '🔬', description: 'Topics, experiments, learning' },
  { id: 'infrastructure', label: 'Infrastructure', icon: '🏠', description: 'Home network, smart home, servers' },
];

export function OnboardingWizard({ onComplete, onSkip }: OnboardingWizardProps) {
  const [step, setStep] = useState(1);
  const [selectedDomains, setSelectedDomains] = useState<string[]>([]);
  const [customSources, setCustomSources] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const toggleDomain = (domainId: string) => {
    setSelectedDomains(prev => 
      prev.includes(domainId)
        ? prev.filter(d => d !== domainId)
        : [...prev, domainId]
    );
  };

  const handleStart = async () => {
    if (selectedDomains.length === 0) return;
    
    setIsLoading(true);
    
    try {
      // Call onboarding API
      const response = await fetch('/api/onboarding/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          domains: selectedDomains,
          sources: customSources ? customSources.split(',').map(s => s.trim()) : []
        })
      });
      
      if (response.ok && onComplete) {
        onComplete(selectedDomains, customSources ? customSources.split(',').map(s => s.trim()) : []);
      }
    } catch (error) {
      console.error('Onboarding start failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="onboarding-wizard">
      {/* Step 1: Welcome */}
      {step === 1 && (
        <div className="step step-1">
          <h2>Welcome to Kitty</h2>
          <p>Let's get to know each other. Pick areas you're interested in, and Kitty will learn about your world.</p>
          <button onClick={() => setStep(2)}>Get Started</button>
        </div>
      )}

      {/* Step 2: Domain Selection */}
      {step === 2 && (
        <div className="step step-2">
          <h3>What matters to you?</h3>
          <p>Select 3+ areas you'd like Kitty to learn about.</p>
          
          <div className="domain-grid">
            {AVAILABLE_DOMAINS.map(domain => (
              <button
                key={domain.id}
                className={`domain-card ${selectedDomains.includes(domain.id) ? 'selected' : ''}`}
                onClick={() => toggleDomain(domain.id)}
              >
                <span className="icon">{domain.icon}</span>
                <span className="label">{domain.label}</span>
                <span className="description">{domain.description}</span>
              </button>
            ))}
          </div>
          
          <div className="actions">
            <button 
              onClick={() => setStep(3)}
              disabled={selectedDomains.length < 1}
            >
              Continue ({selectedDomains.length} selected)
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Sources (optional) */}
      {step === 3 && (
        <div className="step step-3">
          <h3>Any specific sources?</h3>
          <p>Optional: comma-separated URLs, channels, or topics you'd like Kitty to prioritize.</p>
          
          <textarea
            value={customSources}
            onChange={(e) => setCustomSources(e.target.value)}
            placeholder="e.g., r/audioengineering, my YouTube watch later, specific blogs..."
            rows={4}
          />
          
          <div className="actions">
            <button onClick={() => setStep(2)}>Back</button>
            <button 
              onClick={handleStart}
              disabled={isLoading}
            >
              {isLoading ? 'Starting...' : 'Let Kitty Learn'}
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Processing */}
      {step === 4 && isLoading && (
        <div className="step step-4">
          <h3>Kitty is learning...</h3>
          <p>Researching {selectedDomains.join(', ')}</p>
          <div className="progress">
            <div className="progress-bar" />
          </div>
        </div>
      )}

      {/* Skip button */}
      <button className="skip" onClick={onSkip}>
        Skip for now
      </button>
    </div>
  );
}