import React, { useState, useEffect } from 'react';
import { fetchArtifactTypes, publishArtifact, ArtifactType } from '../../services/api';
import { useFilterStore } from '../../store/filterStore';
import { useSettingsStore } from '../../store/settingsStore';
import './PublishControl.css';

interface ValidationErrors {
  artifactType?: string;
  [key: string]: string | undefined; // Allow dynamic field errors
}

interface FormData {
  [key: string]: any;
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
    if (selectedType) {
      const artifactType = artifactTypes.find((t) => t.name === selectedType);
      if (artifactType && artifactType.schema.properties) {
        // Initialize formData with empty values based on schema
        const initialData: FormData = {};
        Object.keys(artifactType.schema.properties).forEach((key) => {
          const prop = artifactType.schema.properties[key];
          if (prop.type === 'boolean') {
            initialData[key] = false;
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

    // Validate each field based on schema
    if (artifactType.schema.properties) {
      Object.entries(artifactType.schema.properties).forEach(([key, prop]: [string, any]) => {
        const value = formData[key];

        // Check required fields (you might need to check schema.required array)
        if (value === '' || value === null || value === undefined) {
          newErrors[key] = `${key} is required`;
          return;
        }

        // Type validation
        if (prop.type === 'number' || prop.type === 'integer') {
          if (isNaN(Number(value))) {
            newErrors[key] = `${key} must be a number`;
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
          if (prop.type === 'number' || prop.type === 'integer') {
            processedData[key] = Number(value);
          } else if (prop.type === 'boolean') {
            processedData[key] = Boolean(value);
          } else {
            processedData[key] = value;
          }
        });
      }

      const response = await publishArtifact(selectedType, processedData);

      // Auto-set filter to correlation ID if checkbox is checked
      if (autoSetFilter && response.correlation_id) {
        useFilterStore.setState({ correlationId: response.correlation_id });
        setSuccessMessage(`Successfully published artifact. Filter set to: ${response.correlation_id}`);
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
  const renderField = (key: string, prop: any) => {
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
              renderField(key, prop)
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
          disabled={loading || loadingTypes}
          className="publish-control__submit"
        >
          {loading ? 'Publishing...' : 'Publish Artifact'}
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
