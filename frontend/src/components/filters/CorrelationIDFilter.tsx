import React, { useState, useRef, useEffect } from 'react';
import { useFilterStore } from '../../store/filterStore';
import styles from './CorrelationIDFilter.module.css';

const formatTimeAgo = (timestamp: number): string => {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
};

const CorrelationIDFilter: React.FC = () => {
  const correlationId = useFilterStore((state) => state.correlationId);
  const availableCorrelationIds = useFilterStore((state) => state.availableCorrelationIds);
  const setCorrelationId = useFilterStore((state) => state.setCorrelationId);

  const [inputValue, setInputValue] = useState(correlationId || '');
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setInputValue(correlationId || '');
  }, [correlationId]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredIds = availableCorrelationIds.filter((item) =>
    item.correlation_id.toLowerCase().includes(inputValue.toLowerCase())
  );

  const handleSelect = (id: string) => {
    setCorrelationId(id);
    setInputValue(id);
    setIsOpen(false);
  };

  const handleClear = () => {
    setCorrelationId(null);
    setInputValue('');
    setIsOpen(false);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
    setIsOpen(true);
  };

  const handleFocus = () => {
    setIsOpen(true);
  };

  const handleBlur = () => {
    // Delay to allow click on dropdown items
    setTimeout(() => setIsOpen(false), 200);
  };

  return (
    <div ref={containerRef} className={styles.container}>
      <div className={styles.inputWrapper}>
        <input
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder="Search correlation ID..."
          className={styles.input}
        />
        {correlationId && (
          <button
            onClick={handleClear}
            aria-label="Clear"
            className={styles.clearButton}
          >
            ×
          </button>
        )}
      </div>

      {isOpen && (
        <div className={styles.dropdown}>
          {filteredIds.length === 0 ? (
            <div className={styles.dropdownEmpty}>
              No correlation IDs found
            </div>
          ) : (
            filteredIds.map((item) => (
              <div
                key={item.correlation_id}
                onClick={() => handleSelect(item.correlation_id)}
                className={styles.dropdownItem}
              >
                <div className={styles.correlationId}>
                  {item.correlation_id}
                </div>
                <div className={styles.metadata}>
                  {item.artifact_count} messages, {formatTimeAgo(item.first_seen)}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default CorrelationIDFilter;
