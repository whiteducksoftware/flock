import React, { useEffect, useState } from 'react';
import type { Node } from '@xyflow/react';
import { type ContractEntry, contractOf } from './contract';
import styles from './Focus.module.css';

const Entry: React.FC<{ entry: ContractEntry }> = ({ entry }) => (
  <div className={styles.card}>
    <div className={styles.cardHead}>
      <span className="mono" title={entry.type}>
        {entry.decision && <span className={styles.diamond}>◆ </span>}
        {entry.label}
      </span>
      {entry.note && <span className={styles.faint}>{entry.note}</span>}
    </div>
    {entry.fields.length > 0 && (
      <div className={`mono ${styles.kv}`}>
        {entry.fields.map((field) => (
          <React.Fragment key={field.name}>
            <span>
              {field.name}
              {!field.required && <span className={styles.faint}>?</span>}
            </span>
            <span>
              {field.type}
              {field.description && <span className={styles.faint}> · {field.description}</span>}
            </span>
          </React.Fragment>
        ))}
      </div>
    )}
  </div>
);

/** What the agent consumes and publishes, with the fields of each type. */
const ContractTab: React.FC<{ id: string; nodes: Node[] }> = ({ id, nodes }) => {
  const [schemas, setSchemas] = useState<Record<string, never> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    fetch('/api/artifact-types')
      .then((response) => {
        if (!response.ok) throw new Error(`The types could not be read (${response.status})`);
        return response.json();
      })
      .then((data: { artifact_types?: { name: string; schema: never }[] }) => {
        if (current) setSchemas(Object.fromEntries((data.artifact_types ?? []).map((type) => [type.name, type.schema])));
      })
      .catch((reason: unknown) => {
        if (current) setError(reason instanceof Error ? reason.message : String(reason));
      });
    return () => {
      current = false;
    };
  }, []);

  if (error) return <div className={styles.empty}>{error}</div>;
  if (schemas === null) return <div className={styles.empty}>Loading the contract…</div>;
  const contract = contractOf(id, nodes, schemas);

  return (
    <div className={styles.contract} data-testid="contract">
      <section className={styles.aside} aria-label="Consumes">
        <span className={styles.label}>Consumes</span>
        {contract.consumes.length === 0 ? (
          <span className={styles.faint}>Nothing: it publishes on its own</span>
        ) : (
          contract.consumes.map((entry) => <Entry key={entry.type} entry={entry} />)
        )}
      </section>
      <section className={styles.aside} aria-label="Publishes">
        <span className={styles.label}>Publishes</span>
        {contract.publishes.length === 0 ? (
          <span className={styles.faint}>Nothing declared</span>
        ) : (
          contract.publishes.map((entry) => <Entry key={entry.type} entry={entry} />)
        )}
      </section>
    </div>
  );
};

export default ContractTab;
