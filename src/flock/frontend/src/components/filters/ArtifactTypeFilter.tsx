import React from 'react';
import MultiSelect from '../settings/MultiSelect';
import { useFilterStore } from '../../store/filterStore';

const ArtifactTypeFilter: React.FC = () => {
  const options = useFilterStore((state) => state.availableArtifactTypes);
  const selected = useFilterStore((state) => state.selectedArtifactTypes);
  const setArtifactTypes = useFilterStore((state) => state.setArtifactTypes);

  return (
    <MultiSelect
      options={options}
      selected={selected}
      onChange={setArtifactTypes}
      placeholder={options.length ? 'Select types…' : 'No types available'}
      disabled={options.length === 0}
    />
  );
};

export default ArtifactTypeFilter;
