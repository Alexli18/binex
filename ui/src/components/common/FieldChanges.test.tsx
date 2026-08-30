import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { FieldChanges } from './FieldChanges';
import type { FieldChange } from '@/hooks/useComparison';

const changed: FieldChange = {
  path: 'decision',
  before: 'approved',
  after: 'rejected',
  kind: 'changed',
};

describe('FieldChanges', () => {
  it('names the field and both values', () => {
    render(<FieldChanges changes={[changed]} />);

    expect(screen.getByText('decision')).toBeInTheDocument();
    expect(screen.getByText(/approved/)).toBeInTheDocument();
    expect(screen.getByText(/rejected/)).toBeInTheDocument();
  });

  it('renders one row per change', () => {
    render(
      <FieldChanges
        changes={[
          changed,
          { path: 'score', before: 0.91, after: 0.42, kind: 'changed' },
        ]}
      />
    );

    expect(screen.getAllByTestId('field-change-row')).toHaveLength(2);
  });

  it('marks an added field as absent before', () => {
    render(
      <FieldChanges
        changes={[{ path: 'notes', before: null, after: 'see log', kind: 'added' }]}
      />
    );

    expect(screen.getByText('added')).toBeInTheDocument();
    expect(screen.getByText(/absent/)).toBeInTheDocument();
  });

  it('marks a removed field as absent after', () => {
    render(
      <FieldChanges
        changes={[{ path: 'notes', before: 'see log', after: null, kind: 'removed' }]}
      />
    );

    expect(screen.getByText('removed')).toBeInTheDocument();
    expect(screen.getByText(/absent/)).toBeInTheDocument();
  });

  it('renders non-string values readably', () => {
    render(
      <FieldChanges
        changes={[{ path: 'is_safe', before: true, after: false, kind: 'changed' }]}
      />
    );

    expect(screen.getByText(/true/)).toBeInTheDocument();
    expect(screen.getByText(/false/)).toBeInTheDocument();
  });

  it('says so when structured content is identical', () => {
    render(<FieldChanges changes={[]} />);

    expect(screen.getByText(/no field changes/i)).toBeInTheDocument();
  });

  it('uses dotted paths for nested fields', () => {
    render(
      <FieldChanges
        changes={[{ path: 'totals.q1', before: 10, after: 99, kind: 'changed' }]}
      />
    );

    expect(screen.getByText('totals.q1')).toBeInTheDocument();
  });
});
