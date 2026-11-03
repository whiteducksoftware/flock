/**
 * The composer's type list: a search, "Your types", "Decisions" and the
 * collapsed "System types". Arrow keys move through the types and pick them.
 *
 * The system types are a listbox of their own: the button that expands them
 * cannot sit inside a listbox. The arrow keys go on from one into the other.
 */

import React, { useId, useRef, useState } from 'react';
import type { ArtifactType } from '../../services/api';
import { shortTypeName } from '../../utils/typeName';
import { Icon } from '../icons/Icon';
import { fieldCount, groupTypes, isDecisionType } from './typeGroups';
import styles from './PublishComposer.module.css';

interface TypeListProps {
  types: ArtifactType[];
  loading: boolean;
  selected: string;
  /** No other type can be picked (while publishing) */
  disabled: boolean;
  onSelect: (name: string) => void;
  searchRef: React.RefObject<HTMLInputElement | null>;
}

const TypeList: React.FC<TypeListProps> = ({ types, loading, selected, disabled, onSelect, searchRef }) => {
  const [query, setQuery] = useState('');
  const [systemOpen, setSystemOpen] = useState(false);
  const options = useRef(new Map<string, HTMLDivElement>());
  const ids = useId();
  const { yours, decisions, system } = groupTypes(types, query);
  const visible = [...yours, ...decisions, ...(systemOpen ? system : [])];
  // One tab stop for the list: the picked type, else the first one
  const tabStop = visible.some((type) => type.name === selected) ? selected : visible[0]?.name;

  const pick = (name: string) => {
    if (!disabled) onSelect(name);
  };

  const moveTo = (index: number) => {
    const type = visible[Math.max(0, Math.min(visible.length - 1, index))];
    if (!type) return;
    pick(type.name);
    const option = options.current.get(type.name);
    option?.focus();
    option?.scrollIntoView?.({ block: 'nearest' });
  };

  const onOptionKeyDown = (event: React.KeyboardEvent, index: number) => {
    if (event.ctrlKey || event.metaKey || event.altKey) return; // Ctrl+Enter publishes
    if (event.key === 'ArrowUp' && index === 0) {
      event.preventDefault();
      searchRef.current?.focus();
      return;
    }
    const targets: Record<string, number> = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: visible.length - 1 };
    const target = targets[event.key];
    if (target !== undefined) {
      event.preventDefault();
      moveTo(target);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      pick(visible[index]!.name);
    }
  };

  const option = (type: ArtifactType) => {
    const index = visible.indexOf(type);
    const decision = isDecisionType(type.name);
    const count = fieldCount(type);
    // A decision's fields are the same for every question: no count (as in the mockup)
    const fields = decision ? null : `${count} ${count === 1 ? 'field' : 'fields'}`;
    return (
      <div
        key={type.name}
        ref={(element) => {
          if (element) options.current.set(type.name, element);
          else options.current.delete(type.name);
        }}
        role="option"
        // "SupportTicket, 2 fields": the two spans would run together
        aria-label={fields ? `${shortTypeName(type.name)}, ${fields}` : shortTypeName(type.name)}
        aria-selected={type.name === selected}
        aria-disabled={disabled || undefined}
        tabIndex={type.name === tabStop ? 0 : -1}
        title={type.name}
        className={styles.type}
        onClick={() => pick(type.name)}
        onKeyDown={(event) => onOptionKeyDown(event, index)}
      >
        {decision && (
          <span className={styles.diamond} aria-hidden>
            ◆
          </span>
        )}
        <span className={`mono ${styles.typeName}`}>{shortTypeName(type.name)}</span>
        {fields && <span className={`mono num ${styles.count}`}>{fields}</span>}
      </div>
    );
  };

  const group = (key: string, label: string, members: ArtifactType[]) =>
    members.length > 0 && (
      <div role="group" aria-labelledby={`${ids}-${key}`}>
        <div id={`${ids}-${key}`} className={styles.groupLabel}>
          {label}
        </div>
        {members.map(option)}
      </div>
    );

  return (
    <div className={styles.types}>
      <label className={styles.search}>
        <Icon name="search" size={14} />
        <span className={styles.srOnly}>Find a type</span>
        <input
          ref={searchRef}
          type="text"
          placeholder="Find a type"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            // A search shows the system types it finds
            if (event.target.value.trim() && groupTypes(types, event.target.value).system.length > 0) {
              setSystemOpen(true);
            }
          }}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' && visible.length > 0) {
              event.preventDefault();
              moveTo(0);
            }
          }}
        />
      </label>

      {loading ? (
        <p className={styles.listNote}>Loading types…</p>
      ) : (
        visible.length === 0 &&
        system.length === 0 && <p className={styles.listNote}>{query ? 'No type matches.' : 'No types yet.'}</p>
      )}

      <div role="listbox" aria-label="Artifact types" className={styles.listbox}>
        {group('yours', 'Your types', yours)}
        {group('decisions', 'Decisions', decisions)}
      </div>

      {system.length > 0 && (
        <>
          <button
            type="button"
            className={`${styles.type} ${styles.systemToggle}`}
            aria-expanded={systemOpen}
            aria-controls={`${ids}-system`}
            onClick={() => setSystemOpen((open) => !open)}
          >
            <Icon name="chevronRight" size={12} className={styles.chevron} />
            <span>System types</span>{' '}
            <span className={`mono num ${styles.count}`}>{system.length}</span>
          </button>
          {systemOpen && (
            <div id={`${ids}-system`} role="listbox" aria-label="System types" className={styles.listbox}>
              {system.map(option)}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default TypeList;
