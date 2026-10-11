import React, { useState, useEffect, useRef } from 'react';
import { fetchArtifactTypes, publishArtifact, ArtifactType } from '../../services/api';
import { useFilterStore } from '../../store/filterStore';
import { useSettingsStore } from '../../store/settingsStore';
import { IMAGE_ACCEPT, fileToImageUrl, imageFieldKind, isNullable } from '../../utils/imageFields';
import './PublishControl.css';

interface ValidationErrors {
  artifactType?: string;
  [key: string]: string | undefined; // Allow dynamic field errors
}

interface FormData {
  [key: string]: any;
}

/** A picture chosen in the form: shown as a preview, published as an Image. */
interface PickedImage {
  name: string;
  url: string;
}

const PublishControl: React.FC = () => {
  const [artifactTypes, setArtifactTypes] = useState<ArtifactType[]>([]);
  const [selectedType, setSelectedType] = useState('');
  const [formData, setFormData] = useState<FormData>({});
  const [loading, setLoading] = useState(false);
  const [loadingTypes, setLoadingTypes] = useState(true);
  const [errors, setErrors] = useState<ValidationErrors>({});
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [autoSetFilter, setAutoSetFilter] = useState(false); // Default: unchecked (user can opt-in to auto-filter)
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

  const handleClose = () => {
    setShowControls(false);
  };

  // Fetch artifact types on mount
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
  }, []);

  // Reset form data when artifact type changes
  useEffect(() => {
    typeGeneration.current += 1;
    fieldGeneration.current = {};
    setPendingConversions({});
    if (selectedType) {
      const artifactType = artifactTypes.find((t) => t.name === selectedType);
      if (artifactType && artifactType.schema.properties) {
        // Initialize formData with empty values based on schema
        const initialData: FormData = {};
        Object.keys(artifactType.schema.properties).forEach((key) => {
          const prop = artifactType.schema.properties[key];
          const imageKind = imageFieldKind(prop, artifactType.schema);
          if (imageKind) {
            initialData[key] = imageKind === 'many' ? [] : null;
          } else if (prop.type === 'boolean') {
            initialData[key] = false;
          } else if (prop.type === 'array') {
            // Represent arrays (e.g. list[str] / list[int]) as a newline-separated string in the UI.
            // If the schema has a default (e.g. default_factory=list), show it to the user.
            if (Array.isArray(prop.default)) {
              initialData[key] = prop.default.join('\n');
            } else {
              initialData[key] = '';
            }
          } else if (prop.type === 'number' || prop.type === 'integer') {
            initialData[key] = prop.default ?? '';
          } else {
            initialData[key] = prop.default ?? '';
          }
        });
        setFormData(initialData);
      }
    } else {
      setFormData({});
    }
    setErrors({});
  }, [selectedType, artifactTypes]);

  const validateForm = (): boolean => {
    const newErrors: ValidationErrors = {};

    if (!selectedType) {
      newErrors.artifactType = 'Artifact type is required';
      setErrors(newErrors);
      return false;
    }

    const artifactType = artifactTypes.find((t) => t.name === selectedType);
    if (!artifactType) {
      newErrors.artifactType = 'Invalid artifact type';
      setErrors(newErrors);
      return false;
    }

    // JSON Schema may include a "required" array listing required fields.
    // Fall back to empty array if not present.
    const requiredFields: string[] = Array.isArray((artifactType.schema as any).required)
      ? (artifactType.schema as any).required
      : [];

    // Validate each field based on schema
    if (artifactType.schema.properties) {
      Object.entries(artifactType.schema.properties).forEach(([key, prop]: [string, any]) => {
        const value = formData[key];

        const isExplicitlyRequired = requiredFields.includes(key);
        const hasDefault = prop.default !== undefined;

        // Image fields: a picture must be chosen unless the field is optional
        const imageKind = imageFieldKind(prop, artifactType.schema);
        if (imageKind === 'many') {
          // An empty list is valid unless the schema asks for a minimum
          const arraySchema = prop.anyOf?.find((option: any) => option?.type === 'array') ?? prop;
          const minItems = arraySchema.minItems ?? 0;
          if ((value?.length ?? 0) < minItems) {
            newErrors[key] = `${key} needs at least ${minItems} picture${minItems === 1 ? '' : 's'}`;
          }
          return;
        }
        if (imageKind === 'one') {
          const required = isExplicitlyRequired || !hasDefault;
          // A required field that may be None is valid without a picture (null)
          if (!value && required && !isNullable(prop)) {
            newErrors[key] = `${key} is required`;
          }
          return;
        }

        // Required heuristic:
        // - If schema.required lists the field, it's required.
        // - If field has an explicit default, treat as optional.
        // - Arrays default to optional unless explicitly required.
        // - Scalar fields with no default are treated as required.
        const isRequired =
          isExplicitlyRequired ||
          (!hasDefault && prop.type !== 'array');

        // Check required fields based on JSON Schema "required"
        if (isRequired && (value === '' || value === null || value === undefined)) {
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
            const parts = value
              .split('\n')
              .map((v: string) => v.trim())
              .filter((v: string) => v.length > 0);
            const invalid = parts.some((v: string) => Number.isNaN(Number(v)));
            if (invalid) {
              newErrors[key] = `${key} must be a list of numbers (one per line)`;
            }
          }
        }
      });
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Clear previous messages
    setSuccessMessage('');
    setErrorMessage('');

    // A picture still being converted would be missing from the request
    if (pendingPictures > 0) {
      return;
    }

    // Validate form
    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      // Convert formData values to proper types
      const artifactType = artifactTypes.find((t) => t.name === selectedType);
      const processedData: any = {};

      if (artifactType && artifactType.schema.properties) {
        Object.entries(formData).forEach(([key, value]) => {
          const prop = artifactType.schema.properties[key];
          if (!prop) return; // not a field of this type
          const imageKind = imageFieldKind(prop, artifactType.schema);
          if (imageKind === 'many') {
            const images = value as PickedImage[];
            // No pictures chosen: keep the schema default (e.g. None or a preset list)
            if (images.length > 0 || prop.default === undefined) {
              processedData[key] = images.map((image) => ({ url: image.url }));
            }
          } else if (imageKind === 'one') {
            if (value) {
              processedData[key] = { url: (value as PickedImage).url };
            } else if (isNullable(prop) && prop.default === undefined) {
              processedData[key] = null; // required, but may be None
            } // otherwise the schema default applies
          } else if (prop.type === 'number' || prop.type === 'integer') {
            processedData[key] = Number(value);
          } else if (prop.type === 'boolean') {
            processedData[key] = Boolean(value);
          } else if (prop.type === 'array') {
            // Convert newline-separated string into arrays for list-like fields
            if (prop.items && prop.items.type === 'string') {
              if (typeof value === 'string') {
                const parts = value
                  .split('\n')
                  .map((v: string) => v.trim())
                  .filter((v: string) => v.length > 0);
                processedData[key] = parts;
              } else if (Array.isArray(value)) {
                processedData[key] = value;
              } else {
                processedData[key] = [];
              }
            } else if (prop.items && (prop.items.type === 'number' || prop.items.type === 'integer')) {
              if (typeof value === 'string') {
                const parts = value
                  .split('\n')
                  .map((v: string) => v.trim())
                  .filter((v: string) => v.length > 0);
                const numbers = parts
                  .map((v: string) => Number(v))
                  .filter((v: number) => !Number.isNaN(v));
                processedData[key] = numbers;
              } else if (Array.isArray(value)) {
                processedData[key] = value.map((v: any) => Number(v));
              } else {
                processedData[key] = [];
              }
            } else {
              // For other array item types, pass through as-is for now
              processedData[key] = value;
            }
          } else {
            processedData[key] = value;
          }
        });
      }

      const response = await publishArtifact(selectedType, processedData);

      // Auto-set filter to correlation ID if checkbox is checked
      if (autoSetFilter && response.correlation_id) {
        useFilterStore.setState({ correlationId: response.correlation_id });
        // Show a concise message focused on the filter for this mode
        setSuccessMessage(`Filter set to: ${response.correlation_id}`);
      } else {
        setSuccessMessage(`Successfully published artifact. Correlation ID: ${response.correlation_id}`);
      }

      // Reset form
      setSelectedType('');
      setFormData({});
      setErrors({});

      // Auto-close the panel after a brief delay to show success message
      setTimeout(() => {
        setShowControls(false);
      }, 800);
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

  // Helper to render form field based on schema property type
  const renderField = (key: string, prop: any, schema: any) => {
    const value = formData[key] ?? '';
    const hasError = !!errors[key];

    const handleChange = (newValue: any) => {
      setFormData({ ...formData, [key]: newValue });
      if (errors[key]) {
        const newErrors = { ...errors };
        delete newErrors[key];
        setErrors(newErrors);
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
          setErrors((previous) => {
            const next = { ...previous };
            delete next[key];
            return next;
          });
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

      // $ref fields carry no title in the schema: fall back to the field name
      const title = prop.title || key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
      return (
        <div key={key} className="publish-control__field">
          <label htmlFor={`field-${key}`} className="publish-control__label">
            {title}
            {prop.description && (
              <span className="publish-control__field-hint"> — {prop.description}</span>
            )}
            <span className="publish-control__field-hint"> — scaled to 1024 px</span>
          </label>
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
            className="publish-control__file-input"
          />
          <button
            type="button"
            onClick={() => document.getElementById(`field-${key}`)?.click()}
            disabled={loading}
            className={`publish-control__file-button ${hasError ? 'publish-control__input--error' : ''}`}
          >
            {imageKind === 'many' ? 'Add images…' : images.length ? 'Replace image…' : 'Choose image…'}
          </button>
          {images.length > 0 && (
            <div className="publish-control__images">
              {images.map((image, index) => (
                <figure key={`${image.name}-${index}`} className="publish-control__image">
                  <img src={image.url} alt={image.name} />
                  <button
                    type="button"
                    onClick={() => removeImage(index)}
                    disabled={loading}
                    aria-label={`Remove ${image.name}`}
                    className="publish-control__image-remove"
                  >
                    ×
                  </button>
                </figure>
              ))}
            </div>
          )}
          {hasError && <div className="publish-control__error-text">{errors[key]}</div>}
        </div>
      );
    }

    if (prop.type === 'boolean') {
      return (
        <div key={key} className="publish-control__field">
          <div className="publish-control__checkbox-wrapper">
            <input
              type="checkbox"
              id={`field-${key}`}
              checked={Boolean(value)}
              onChange={(e) => handleChange(e.target.checked)}
              disabled={loading}
              className="publish-control__checkbox"
            />
            <label htmlFor={`field-${key}`} className="publish-control__checkbox-label">
              {prop.title || key}
              {prop.description && (
                <span className="publish-control__field-hint"> — {prop.description}</span>
              )}
            </label>
          </div>
          {hasError && <div className="publish-control__error-text">{errors[key]}</div>}
        </div>
      );
    }

    // Arrays of strings: use a textarea where each line is one item.
    if (prop.type === 'array' && prop.items && prop.items.type === 'string') {
      return (
        <div key={key} className="publish-control__field">
          <label htmlFor={`field-${key}`} className="publish-control__label">
            {prop.title || key}
            {prop.description && (
              <span className="publish-control__field-hint"> — {prop.description}</span>
            )}
            <span className="publish-control__field-hint">
              {' '}
              — One item per line
            </span>
          </label>
          <textarea
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            rows={3}
            className={`publish-control__textarea ${hasError ? 'publish-control__textarea--error' : ''}`}
          />
          {hasError && <div className="publish-control__error-text">{errors[key]}</div>}
        </div>
      );
    }

    // Arrays of numbers/integers: textarea, one number per line.
    if (prop.type === 'array' && prop.items && (prop.items.type === 'number' || prop.items.type === 'integer')) {
      return (
        <div key={key} className="publish-control__field">
          <label htmlFor={`field-${key}`} className="publish-control__label">
            {prop.title || key}
            {prop.description && (
              <span className="publish-control__field-hint"> — {prop.description}</span>
            )}
            <span className="publish-control__field-hint">
              {' '}
              — One number per line
            </span>
          </label>
          <textarea
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            rows={3}
            className={`publish-control__textarea ${hasError ? 'publish-control__textarea--error' : ''}`}
          />
          {hasError && <div className="publish-control__error-text">{errors[key]}</div>}
        </div>
      );
    }

    if (prop.type === 'number' || prop.type === 'integer') {
      return (
        <div key={key} className="publish-control__field">
          <label htmlFor={`field-${key}`} className="publish-control__label">
            {prop.title || key}
            {prop.description && (
              <span className="publish-control__field-hint"> — {prop.description}</span>
            )}
          </label>
          <input
            type="number"
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            step={prop.type === 'integer' ? 1 : 'any'}
            className={`publish-control__input ${hasError ? 'publish-control__input--error' : ''}`}
          />
          {hasError && <div className="publish-control__error-text">{errors[key]}</div>}
        </div>
      );
    }

    if (prop.enum && Array.isArray(prop.enum)) {
      return (
        <div key={key} className="publish-control__field">
          <label htmlFor={`field-${key}`} className="publish-control__label">
            {prop.title || key}
            {prop.description && (
              <span className="publish-control__field-hint"> — {prop.description}</span>
            )}
          </label>
          <select
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            className={`publish-control__select ${hasError ? 'publish-control__select--error' : ''}`}
          >
            <option value="">Select...</option>
            {prop.enum.map((option: any) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {hasError && <div className="publish-control__error-text">{errors[key]}</div>}
        </div>
      );
    }

    // Default: text input or textarea for strings
    const isLongText = prop.maxLength > 100 || key.toLowerCase().includes('description');

    if (isLongText) {
      return (
        <div key={key} className="publish-control__field">
          <label htmlFor={`field-${key}`} className="publish-control__label">
            {prop.title || key}
            {prop.description && (
              <span className="publish-control__field-hint"> — {prop.description}</span>
            )}
          </label>
          <textarea
            id={`field-${key}`}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            disabled={loading}
            rows={4}
            className={`publish-control__textarea ${hasError ? 'publish-control__textarea--error' : ''}`}
          />
          {hasError && <div className="publish-control__error-text">{errors[key]}</div>}
        </div>
      );
    }

    return (
      <div key={key} className="publish-control__field">
        <label htmlFor={`field-${key}`} className="publish-control__label">
          {prop.title || key}
          {prop.description && (
            <span className="publish-control__field-hint"> — {prop.description}</span>
          )}
        </label>
        <input
          type="text"
          id={`field-${key}`}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          disabled={loading}
          placeholder={prop.examples?.[0] || ''}
          className={`publish-control__input ${hasError ? 'publish-control__input--error' : ''}`}
        />
        {hasError && <div className="publish-control__error-text">{errors[key]}</div>}
      </div>
    );
  };

  return (
    <div className="publish-control-panel">
      <div className="publish-control-panel-inner">
        {/* Header */}
        <div className="publish-control-header">
          <h2 className="publish-control-title">Publish Artifact</h2>
          <button
            onClick={handleClose}
            className="publish-control-close-button"
            aria-label="Close publish panel"
            title="Close publish panel (Esc)"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path
                d="M15 5L5 15M5 5l10 10"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="publish-control-content">
          <form className="publish-control__form" onSubmit={handleSubmit}>
        {/* Artifact Type Dropdown */}
        <div className="publish-control__field">
          <label htmlFor="artifact-type" className="publish-control__label">
            Artifact Type
          </label>
          <select
            id="artifact-type"
            value={selectedType}
            onChange={(e) => {
              setSelectedType(e.target.value);
              setErrors({ ...errors, artifactType: undefined });
            }}
            disabled={loadingTypes || loading}
            className={`publish-control__select ${errors.artifactType ? 'publish-control__select--error' : ''}`}
          >
            <option value="">Select an artifact type...</option>
            {artifactTypes.map((type) => (
              <option key={type.name} value={type.name}>
                {type.name}
              </option>
            ))}
          </select>
          {errors.artifactType && (
            <div className="publish-control__error-text">
              {errors.artifactType}
            </div>
          )}
        </div>

        {/* Dynamic Form Fields based on Schema */}
        {selectedType && (() => {
          const artifactType = artifactTypes.find((t) => t.name === selectedType);
          if (artifactType && artifactType.schema.properties) {
            return Object.entries(artifactType.schema.properties).map(([key, prop]) =>
              renderField(key, prop, artifactType.schema)
            );
          }
          return (
            <div className="publish-control__field">
              <p className="publish-control__hint">
                Select an artifact type to see form fields
              </p>
            </div>
          );
        })()}

        {/* Auto-set Filter Checkbox */}
        <div className="publish-control__checkbox-wrapper">
          <input
            type="checkbox"
            id="auto-set-filter"
            checked={autoSetFilter}
            onChange={(e) => setAutoSetFilter(e.target.checked)}
            disabled={loading}
            className="publish-control__checkbox"
          />
          <label htmlFor="auto-set-filter" className="publish-control__checkbox-label">
            Set filter to correlation ID (show only this execution)
          </label>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || loadingTypes || pendingPictures > 0}
          className="publish-control__submit"
        >
          {pendingPictures > 0 ? 'Processing pictures…' : loading ? 'Publishing...' : 'Publish Artifact'}
        </button>

        {/* Success Message */}
        {successMessage && (
          <div className="publish-control__message publish-control__message--success">
            {successMessage}
          </div>
        )}

        {/* Error Message */}
        {errorMessage && (
          <div className="publish-control__message publish-control__message--error">
            {errorMessage}
          </div>
        )}
          </form>
        </div>
      </div>
    </div>
  );
};

export default PublishControl;
