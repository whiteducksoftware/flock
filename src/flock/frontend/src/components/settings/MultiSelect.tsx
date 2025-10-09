/**
 * Multi-Select Component with Autocomplete
 *
 * Elegant multi-select dropdown with:
 * - Autocomplete filtering
 * - Tag-based selection display
 * - Keyboard navigation
 * - Remove on click
 */

import React, { useState, useRef, useEffect } from 'react';

interface MultiSelectProps {
  options: string[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
}

const MultiSelect: React.FC<MultiSelectProps> = ({
  options,
  selected,
  onChange,
  placeholder = 'Select items...',
  disabled = false
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Filter options based on search term and exclude already selected
  const filteredOptions = options.filter(
    option =>
      !selected.includes(option) &&
      option.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (option: string) => {
    onChange([...selected, option]);
    setSearchTerm('');
    setFocusedIndex(0);
    inputRef.current?.focus();
  };

  const handleRemove = (option: string) => {
    onChange(selected.filter(item => item !== option));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex(prev => Math.min(prev + 1, filteredOptions.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filteredOptions[focusedIndex]) {
          handleSelect(filteredOptions[focusedIndex]);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        setSearchTerm('');
        break;
      case 'Backspace':
        if (searchTerm === '' && selected.length > 0) {
          const lastItem = selected[selected.length - 1];
          if (lastItem) {
            handleRemove(lastItem);
          }
        }
        break;
    }
  };

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      {/* Input Container with Tags */}
      <div
        onClick={() => !disabled && inputRef.current?.focus()}
        style={{
          minHeight: '38px',
          padding: 'var(--space-xs)',
          backgroundColor: disabled ? 'rgba(0, 0, 0, 0.2)' : 'rgba(0, 0, 0, 0.3)',
          border: `1px solid ${isOpen ? 'rgba(96, 165, 250, 0.5)' : 'rgba(255, 255, 255, 0.1)'}`,
          borderRadius: 'var(--radius-sm)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 'var(--gap-xs)',
          cursor: disabled ? 'not-allowed' : 'text',
          transition: 'border-color 0.2s',
          opacity: disabled ? 0.6 : 1
        }}
      >
        {/* Selected Tags */}
        {selected.map(item => (
          <div
            key={item}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--gap-xs)',
              padding: '2px 8px',
              backgroundColor: 'rgba(96, 165, 250, 0.2)',
              border: '1px solid rgba(96, 165, 250, 0.4)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 'var(--font-size-sm)',
              color: '#60a5fa',
              maxWidth: '100%',
              overflow: 'hidden'
            }}
          >
            <span style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              minWidth: 0
            }} title={item}>
              {item}
            </span>
            {!disabled && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleRemove(item);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#60a5fa',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: '14px',
                  lineHeight: 1,
                  flexShrink: 0
                }}
              >
                ×
              </button>
            )}
          </div>
        ))}

        {/* Search Input */}
        <input
          ref={inputRef}
          type="text"
          value={searchTerm}
          onChange={(e) => {
            setSearchTerm(e.target.value);
            setIsOpen(true);
            setFocusedIndex(0);
          }}
          onFocus={() => !disabled && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={selected.length === 0 ? placeholder : ''}
          disabled={disabled}
          style={{
            flex: 1,
            minWidth: '120px',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--color-text-primary)',
            fontSize: 'var(--font-size-base)',
            padding: '4px'
          }}
        />
      </div>

      {/* Dropdown Options */}
      {isOpen && !disabled && filteredOptions.length > 0 && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            maxHeight: '240px',
            overflowY: 'auto',
            backgroundColor: 'rgba(0, 0, 0, 0.9)',
            border: '1px solid rgba(96, 165, 250, 0.3)',
            borderRadius: 'var(--radius-sm)',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
            zIndex: 1000
          }}
        >
          {filteredOptions.map((option, index) => (
            <div
              key={option}
              onClick={() => handleSelect(option)}
              onMouseEnter={() => setFocusedIndex(index)}
              style={{
                padding: 'var(--space-xs) var(--space-sm)',
                cursor: 'pointer',
                backgroundColor: index === focusedIndex ? 'rgba(96, 165, 250, 0.2)' : 'transparent',
                color: index === focusedIndex ? '#60a5fa' : 'var(--color-text-primary)',
                fontSize: 'var(--font-size-sm)',
                transition: 'background-color 0.15s'
              }}
            >
              {option}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default MultiSelect;
