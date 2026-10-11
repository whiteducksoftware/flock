/**
 * The publish composer: pick a type, fill in its form or JSON, see which
 * agents pick it up, publish with Ctrl/⌘+Enter
 * (docs/internal/design-system/README.md, Overlays; mockups/Publish.dc.html).
 */

import React, { useEffect, useId, useRef, useState } from 'react';
import { fetchAgents, fetchArtifactTypes, publishArtifact, type Agent, type ArtifactType } from '../../services/api';
import { useFilterStore } from '../../store/filterStore';
import { useSettingsStore } from '../../store/settingsStore';
import { useUIStore } from '../../store/uiStore';
import { IMAGE_ACCEPT, fileToImageUrl, imageFieldKind } from '../../utils/imageFields';
import { shortTypeName } from '../../utils/typeName';
import { shortId } from '../graph/unfold/format';
import { Icon } from '../icons/Icon';
import {
  type FormValues,
  type PickedImage,
  type Schema,
  fieldType,
  formToPayload,
  initialFormData,
  isRequiredField,
  lines,
  minPictures,
  payloadToForm,
} from './form';
import PickedUpBy from './PickedUpBy';
import { schemaErrors } from './schemaErrors';
import TypeList from './TypeList';
import styles from './PublishComposer.module.css';

interface ValidationErrors {
  artifactType?: string;
  [key: string]: string | undefined; // Allow dynamic field errors
}

type EditorMode = 'form' | 'json';

const pretty = (value: unknown) => JSON.stringify(value, null, 2);

/** The JSON of the editor as a value, or why it does not parse. */
function parseJson(text: string): { value: unknown } | { error: string } {
  try {
    return { value: JSON.parse(text) };
  } catch (error: any) {
    return { error: `The JSON does not parse: ${error.message}` };
  }
}

const PublishComposer: React.FC = () => {
  const [artifactTypes, setArtifactTypes] = useState<ArtifactType[]>([]);
  // The agents, read once, for "Picked up by"; null until they arrive
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [selectedType, setSelectedType] = useState('');
  const [formData, setFormData] = useState<FormValues>({});
  const [mode, setMode] = useState<EditorMode>('form');
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingTypes, setLoadingTypes] = useState(true);
  const [errors, setErrors] = useState<ValidationErrors>({});
  const [errorMessage, setErrorMessage] = useState('');
  const [follow, setFollow] = useState(true);
  // Picture conversions finish asynchronously: these counters let a result land
  // only if no newer choice (or another artifact type) replaced it meanwhile
  const typeGeneration = useRef(0);
  const fieldGeneration = useRef<Record<string, number>>({});
  // Conversions in progress, per field; a replaced or abandoned one drops out at once
  const [pendingConversions, setPendingConversions] = useState<Record<string, number[]>>({});
  const pendingPictures = Object.values(pendingConversions).reduce(
    (count, tokens) => count + tokens.length,
    0
  );

  const setShowControls = useSettingsStore((state) => state.setShowControls);
  const showToast = useUIStore((state) => state.showToast);
  const dialogRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const ids = useId();
  // Whatever had the focus before the composer opened gets it back
  const [opener] = useState(() => document.activeElement as HTMLElement | null);

  const artifactType = artifactTypes.find((t) => t.name === selectedType);
  const schema = artifactType?.schema as Schema | undefined;

  const handleClose = () => {
    setShowControls(false);
  };

  // The type search takes the focus
  useEffect(() => {
    searchRef.current?.focus();
    return () => opener?.focus?.();
  }, [opener]);

  // Fetch artifact types and agents on mount
  useEffect(() => {
    const loadArtifactTypes = async () => {
      try {
        setLoadingTypes(true);
        const types = await fetchArtifactTypes();
        setArtifactTypes(types);
      } catch (error) {
        console.error('Failed to fetch artifact types:', error);
        setErrorMessage('Failed to load artifact types');
      } finally {
        setLoadingTypes(false);
      }
    };

    loadArtifactTypes();
    // Without the agents the composer still publishes; it only cannot preview
    fetchAgents()
      .then((list) => setAgents(list ?? []))
      .catch((error) => console.error('Failed to fetch agents:', error));
  }, []);

  // Reset form data when artifact type changes
  useEffect(() => {
    typeGeneration.current += 1;
    fieldGeneration.current = {};
    setPendingConversions({});
    const type = artifactTypes.find((t) => t.name === selectedType);
    const initialData = type ? initialFormData(type.schema) : {};
    setFormData(initialData);
    setJsonText(type ? pretty(formToPayload(initialData, type.schema)) : '');
    setJsonError('');
    setErrors({});
  }, [selectedType, artifactTypes]);

  const clearError = (key: string) =>
    setErrors((previous) => {
      const next = { ...previous };
      delete next[key];
      return next;
    });

  const validateForm = (): boolean => {
    const newErrors: ValidationErrors = {};

    if (!selectedType) {
      newErrors.artifactType = 'Artifact type is required';
      setErrors(newErrors);
      return false;
    }

    if (!artifactType || !schema) {
      newErrors.artifactType = 'Invalid artifact type';
      setErrors(newErrors);
      return false;
    }

    // Validate each field based on schema
    Object.entries(schema.properties ?? {}).forEach(([key, prop]: [string, any]) => {
      const value = formData[key];

      // Image fields: a picture must be chosen unless the field is optional
      const imageKind = imageFieldKind(prop, schema);
      if (imageKind === 'many') {
        // An empty list is valid unless the schema asks for a minimum
        const minItems = minPictures(prop);
        if ((value?.length ?? 0) < minItems) {
          newErrors[key] = `${key} needs at least ${minItems} picture${minItems === 1 ? '' : 's'}`;
        }
        return;
      }
      if (imageKind === 'one') {
        // A required field that may be None is valid without a picture (null)
        if (!value && isRequiredField(key, prop, schema)) {
          newErrors[key] = `${key} is required`;
        }
        return;
      }

      // Check required fields based on JSON Schema "required" (and the defaults)
      if (isRequiredField(key, prop, schema) && (value === '' || value === null || value === undefined)) {
        newErrors[key] = `${key} is required`;
        return;
      }

      // Type validation
      if (prop.type === 'number' || prop.type === 'integer') {
        if (isNaN(Number(value))) {
          newErrors[key] = `${key} must be a number`;
        }
      } else if (prop.type === 'array') {
        // For arrays we expect a newline-separated string in the UI.
        if (typeof value !== 'string') {
          newErrors[key] = `${key} must be a list (one item per line)`;
          return;
        }

        // Optional extra validation for numeric arrays
        if (prop.items && (prop.items.type === 'number' || prop.items.type === 'integer')) {
          const invalid = lines(value).some((v: string) => Number.isNaN(Number(v)));
          if (invalid) {
            newErrors[key] = `${key} must be a list of numbers (one per line)`;
          }
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  /** The payload to send, or null after showing why there is none. */
  const payloadToSend = (): Record<string, any> | null => {
    if (mode === 'form' || !schema) {
      return validateForm() && schema ? formToPayload(formData, schema) : null;
    }
    const parsed = parseJson(jsonText);
    if ('error' in parsed) {
      setJsonError(parsed.error);
      return null;
    }
    const problems = schemaErrors(parsed.value, schema);
    setErrors(problems);
    return Object.keys(problems).length === 0 ? (parsed.value as Record<string, any>) : null;
  };

  const publish = async () => {
    // Clear previous messages
    setErrorMessage('');

    // A picture still being converted would be missing from the request
    if (pendingPictures > 0 || loading) {
      return;
    }

    const payload = payloadToSend();
    if (!payload) {
      return;
    }

    setLoading(true);

    try {
      const response = await publishArtifact(selectedType, payload);
      const correlationId = response.correlation_id;
      const run = shortId(correlationId, 4);
      const following = follow && Boolean(correlationId);

      // Follow the run: the board shows only its correlation ID
      if (following) {
        useFilterStore.getState().setCorrelationId(correlationId);
      }
      showToast({
        message: `Published ${shortTypeName(selectedType)}${run ? ` · run ${run}` : ''}`,
        title: correlationId || undefined,
        ...(following && {
          detail: `Following run ${run}`,
          action: {
            label: 'Stop following',
            onClick: () => {
              // Unless another filter replaced it meanwhile
              if (useFilterStore.getState().correlationId === correlationId) {
                useFilterStore.getState().setCorrelationId(null);
              }
            },
          },
        }),
      });

      // Reset form
      setSelectedType('');
      setMode('form');
      setFormData({});
      setErrors({});
      handleClose();
    } catch (error: any) {
      // Handle errors
      if (error.message.includes('Network error') || error.message.includes('Failed to connect')) {
        setErrorMessage('Network error. Failed to connect to API server.');
      } else {
        setErrorMessage(error.message || 'Failed to publish artifact');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void publish();
  };

  const showJson = () => {
    if (mode === 'json' || !schema) return;
    setJsonText(pretty(formToPayload(formData, schema)));
    setJsonError('');
    setErrors({});
    setMode('json');
  };

  // Back to the form only with JSON it can show
  const showForm = () => {
    if (mode === 'form' || !schema) return;
    const parsed = parseJson(jsonText);
    if ('error' in parsed) {
      setJsonError(parsed.error);
      return;
    }
    const value = parsed.value;
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      setJsonError('The JSON must be an object to show it as a form');
      return;
    }
    setFormData(payloadToForm(value as Record<string, any>, schema));
    setJsonError('');
    setErrors({});
    setMode('form');
  };

  const onDialogKeyDown = (event: React.KeyboardEvent) => {
    // Ctrl+Enter or ⌘+Enter publishes from anywhere in the composer
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      formRef.current?.requestSubmit();
      return;
    }
    // Modal: Tab and Shift+Tab go round inside it
    if (event.key === 'Tab' && dialogRef.current) {
      // In document order (a selector list may come back grouped by selector)
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('*')).filter((element) =>
        element.matches('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
  };

  // The label of a field: its name, then its type and a description or "required"
  const fieldLabel = (key: string, prop: any, extra?: string) => (
    <label htmlFor={`field-${key}`} className={styles.flabel}>
      <span className="mono">{key}</span>{' '}
      <span className={styles.hint}>
        {[
          fieldType(prop, schema!),
          prop.description || (isRequiredField(key, prop, schema!) ? 'required' : ''),
          extra,
        ]
          .filter(Boolean)
          .join(' · ')}
      </span>
    </label>
  );

  const errorText = (key: string) =>
    errors[key] && (
      <div id={`field-${key}-error`} className={styles.errorText}>
        {errors[key]}
      </div>
    );

  // Helper to render form field based on schema property type
  const renderField = (key: string, prop: any, schema: Schema) => {
    const value = formData[key] ?? '';
    const hasError = !!errors[key];
    const inputClass = `${styles.input} ${hasError ? styles.invalid : ''}`;
    const errorProps = hasError ? { 'aria-invalid': true, 'aria-describedby': `field-${key}-error` } : {};

    const handleChange = (newValue: any) => {
      setFormData({ ...formData, [key]: newValue });
      if (errors[key]) {
        clearError(key);
      }
    };

    const imageKind = imageFieldKind(prop, schema);
    if (imageKind) {
      const images: PickedImage[] =
        imageKind === 'many' ? (formData[key] ?? []) : formData[key] ? [formData[key]] : [];

      const addFiles = async (files: File[]) => {
        if (files.length === 0) return;
        const typeAtStart = typeGeneration.current;
        const fieldAtStart = (fieldGeneration.current[key] ?? 0) + 1;
        fieldGeneration.current[key] = fieldAtStart;
        // Another artifact type, or (for a single picture) a newer choice, won
        const isStale = () =>
          typeGeneration.current !== typeAtStart ||
          (imageKind === 'one' && fieldGeneration.current[key] !== fieldAtStart);
        const token = fieldAtStart;
        setPendingConversions((previous) => ({
          ...previous,
          // A single picture: the newer choice replaces the pending older one
          [key]: imageKind === 'one' ? [token] : [...(previous[key] ?? []), token],
        }));
        try {
          const picked = await Promise.all(
            files.map(async (file) => ({ name: file.name, url: await fileToImageUrl(file) }))
          );
          if (isStale()) return;
          setFormData((previous) => ({
            ...previous,
            [key]: imageKind === 'many' ? [...(previous[key] ?? []), ...picked] : picked[0],
          }));
          clearError(key);
        } catch {
          if (isStale()) return;
          setErrors((previous) => ({ ...previous, [key]: `Could not read the picture for ${key}` }));
        } finally {
          if (typeGeneration.current === typeAtStart) {
            setPendingConversions((previous) => ({
              ...previous,
              [key]: (previous[key] ?? []).filter((pending) => pending !== token),
            }));
          }
        }
      };

      const removeImage = (index: number) => {
        setFormData((previous) => ({
          ...previous,
          [key]:
            imageKind === 'many'
              ? (previous[key] as PickedImage[]).filter((_, i) => i !== index)
              : null,
        }));
      };

      return (
        <div key={key} className={styles.field}>
          {fieldLabel(key, prop, 'scaled to 1024 px')}
          <input
            type="file"
            id={`field-${key}`}
            accept={IMAGE_ACCEPT}
            multiple={imageKind === 'many'}
            disabled={loading}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              e.target.value = '';
              void addFiles(files);
            }}
            className={styles.fileInput}
            {...errorProps}
          />
          <button
            type="button"
            onClick={() => document.getElementById(`field-${key}`)?.click()}
            disabled={loading}
            className={`btn sm ${styles.fileButton} ${hasError ? styles.invalid : ''}`}
          >
            {imageKind === 'many' ? 'Add images…' : images.length ? 'Replace image…' : 'Choose image…'}
          </button>
          {images.length > 0 && (
            <div className={styles.images}>
              {images.map((image, index) => (
                <figure key={`${image.name}-${index}`} className={styles.image}>
                  <img src={image.url} alt={image.name} />
                  <button
                    type="button"
                    onClick={() => removeImage(index)}
                    disabled={loading}
                    aria-label={`Remove ${image.name}`}
                    className={styles.imageRemove}
                  >
                    <Icon name="close" size={12} />
                  </button>
                </figure>
              ))}
            </div>
          )}
          {errorText(key)}
        </div>
      );
    }

    if (prop.type === 'boolean') {
      return (
        <div key={key} className={styles.field}>
          <div className={styles.checkboxField}>
            <input
              type="checkbox"
              id={`field-${key}`}
              checked={Boolean(value)}
              onChange={(e) => handleChange(e.target.checked)}
              disabled={loading}
              className={styles.checkbox}
              {...errorProps}
            />
            {fieldLabel(key, prop)}
          </div>
          {errorText(key)}
        </div>
      );
    }

    // Arrays of strings: use a textarea where each line is one item.
    // Arrays of numbers/integers: textarea, one number per line.
    const listItems =
      prop.type === 'array' && prop.items
        ? prop.items.type === 'string'
          ? 'one item per line'
          : prop.items.type === 'number' || prop.items.type === 'integer'
            ? 'one number per line'
            : null
        : null;
    if (listItems) {
      return (
        <div key={key} className={styles.field}>
          {fieldLabel(key, prop, listItems)}
          <textarea
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            rows={3}
            className={inputClass}
            {...errorProps}
          />
          {errorText(key)}
        </div>
      );
    }

    if (prop.type === 'number' || prop.type === 'integer') {
      return (
        <div key={key} className={styles.field}>
          {fieldLabel(key, prop)}
          <input
            type="number"
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            step={prop.type === 'integer' ? 1 : 'any'}
            className={inputClass}
            {...errorProps}
          />
          {errorText(key)}
        </div>
      );
    }

    if (prop.enum && Array.isArray(prop.enum)) {
      return (
        <div key={key} className={styles.field}>
          {fieldLabel(key, prop)}
          <select
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            className={inputClass}
            {...errorProps}
          >
            <option value="">Select...</option>
            {prop.enum.map((option: any) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {errorText(key)}
        </div>
      );
    }

    // Default: text input or textarea for strings
    const isLongText = prop.maxLength > 100 || key.toLowerCase().includes('description');

    if (isLongText) {
      return (
        <div key={key} className={styles.field}>
          {fieldLabel(key, prop)}
          <textarea
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            rows={4}
            className={inputClass}
            {...errorProps}
          />
          {errorText(key)}
        </div>
      );
    }

    return (
      <div key={key} className={styles.field}>
        {fieldLabel(key, prop)}
        <input
          type="text"
          id={`field-${key}`}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          disabled={loading}
          placeholder={prop.examples?.[0] || ''}
          className={inputClass}
          {...errorProps}
        />
        {errorText(key)}
      </div>
    );
  };

  const jsonProblems = Object.values(errors).filter(Boolean) as string[];

  return (
    <div className={styles.overlay}>
      <div className={styles.scrim} aria-hidden onClick={handleClose} data-testid="publish-scrim" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${ids}-title`}
        aria-describedby={`${ids}-subtitle`}
        className={styles.dialog}
        onKeyDown={onDialogKeyDown}
      >
        <div className={styles.header}>
          <div className={styles.titles}>
            <h2 id={`${ids}-title`} className={styles.title}>
              Publish to the blackboard
            </h2>
            <span id={`${ids}-subtitle`} className={styles.subtitle}>
              Agents subscribed to the type pick it up right away
            </span>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className={`btn icon ghost ${styles.close}`}
            aria-label="Close"
            title="Close (Esc)"
          >
            <Icon name="close" />
          </button>
        </div>

        <div className={styles.body}>
          <TypeList
            types={artifactTypes}
            loading={loadingTypes}
            selected={selectedType}
            disabled={loading}
            onSelect={(name) => {
              setSelectedType(name);
              setErrors({ ...errors, artifactType: undefined });
            }}
            searchRef={searchRef}
          />

          <form ref={formRef} className={styles.main} onSubmit={handleSubmit}>
            {artifactType && schema ? (
              <>
                <div className={styles.head}>
                  <div className={styles.heading}>
                    <span className={`mono ${styles.typeTitle}`} title={artifactType.name}>
                      {shortTypeName(artifactType.name)}
                    </span>
                    {schema.description && <span className={styles.description}>{schema.description}</span>}
                  </div>
                  <div role="group" aria-label="Editor" className={styles.segs}>
                    <button type="button" className="seg" aria-pressed={mode === 'form'} onClick={showForm}>
                      Form
                    </button>
                    <button
                      type="button"
                      className="seg"
                      aria-pressed={mode === 'json'}
                      onClick={showJson}
                      disabled={pendingPictures > 0}
                    >
                      JSON
                    </button>
                  </div>
                </div>

                <div className={styles.content}>
                  {mode === 'form' ? (
                    <div className={styles.fields}>
                      {Object.entries(schema.properties ?? {}).map(([key, prop]) => renderField(key, prop, schema))}
                    </div>
                  ) : (
                    <div className={styles.field}>
                      <label htmlFor="publish-json" className={styles.srOnly}>
                        {shortTypeName(artifactType.name)} as JSON
                      </label>
                      <textarea
                        id="publish-json"
                        value={jsonText}
                        onChange={(e) => {
                          setJsonText(e.target.value);
                          setJsonError('');
                          setErrors({});
                        }}
                        disabled={loading}
                        rows={9}
                        spellCheck={false}
                        className={`mono ${styles.input} ${styles.json} ${jsonError || jsonProblems.length ? styles.invalid : ''}`}
                      />
                      {jsonError && <div className={styles.errorText}>{jsonError}</div>}
                      {jsonProblems.length > 0 && (
                        <ul className={styles.problems}>
                          {jsonProblems.map((problem) => (
                            <li key={problem}>{problem}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

                  {agents && <PickedUpBy typeName={artifactType.name} agents={agents} />}
                </div>
              </>
            ) : (
              <div className={styles.content}>
                <p className={styles.empty}>
                  {loadingTypes ? 'Loading types…' : 'Pick a type to fill in its fields.'}
                </p>
                {errors.artifactType && <div className={styles.errorText}>{errors.artifactType}</div>}
              </div>
            )}

            {errorMessage && (
              <div role="alert" className={styles.message}>
                <Icon name="error" size={15} />
                {errorMessage}
              </div>
            )}

            <div className={styles.footer}>
              <label className={styles.follow}>
                <input
                  type="checkbox"
                  checked={follow}
                  onChange={(e) => setFollow(e.target.checked)}
                  disabled={loading}
                />
                <span>Follow this run on the board</span>
              </label>
              <div className={styles.actions}>
                <button type="button" className="btn ghost" onClick={handleClose}>
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || loadingTypes || pendingPictures > 0}
                  className={`btn primary ${styles.publish}`}
                  aria-keyshortcuts="Control+Enter Meta+Enter"
                >
                  {pendingPictures > 0 ? 'Processing pictures…' : loading ? 'Publishing…' : 'Publish'}
                  {pendingPictures === 0 && !loading && <kbd aria-hidden>⌘↵</kbd>}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default PublishComposer;
