import { useState, useMemo, useCallback } from 'react';
import { Search, BookOpen, X, ArrowLeft, Plus } from 'lucide-react';
import { usePromptTemplates, usePromptTemplateContent, useCreatePromptTemplate } from '../hooks/usePromptTemplates';
import type { PromptTemplate } from '../hooks/usePromptTemplates';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';

// --- Category colors ---

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  Business:    { bg: 'bg-blue-500/10',    text: 'text-blue-400',    border: 'border-blue-500/30' },
  Content:     { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  Data:        { bg: 'bg-orange-500/10',  text: 'text-orange-400',  border: 'border-orange-500/30' },
  Development: { bg: 'bg-purple-500/10',  text: 'text-purple-400',  border: 'border-purple-500/30' },
  Education:   { bg: 'bg-cyan-500/10',    text: 'text-cyan-400',    border: 'border-cyan-500/30' },
  General:     { bg: 'bg-slate-500/10',   text: 'text-slate-400',   border: 'border-slate-500/30' },
  Legal:       { bg: 'bg-red-500/10',     text: 'text-red-400',     border: 'border-red-500/30' },
  Support:     { bg: 'bg-amber-500/10',   text: 'text-amber-400',   border: 'border-amber-500/30' },
  Workflow:    { bg: 'bg-rose-500/10',    text: 'text-rose-400',    border: 'border-rose-500/30' },
};

const DEFAULT_COLORS = { bg: 'bg-slate-500/10', text: 'text-slate-400', border: 'border-slate-500/30' };

function getCategoryColors(category: string) {
  return CATEGORY_COLORS[category] || DEFAULT_COLORS;
}

/** Humanize prompt name: "gen-research-planner" → "Research Planner" */
function humanizeName(name: string): string {
  return name
    .replace(/^(gen|dev|cnt|biz|dat|edu|leg|sup|wf)-/, '')
    .replace(/-/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

// --- PromptCard ---

function PromptCard({
  template,
  isSelected,
  onSelect,
}: {
  template: PromptTemplate;
  isSelected: boolean;
  onSelect: (t: PromptTemplate) => void;
}) {
  const colors = getCategoryColors(template.category);

  return (
    <button
      onClick={() => onSelect(template)}
      className={`group text-left w-full border rounded-lg p-3 transition-all duration-150 ${
        isSelected
          ? 'border-blue-500 bg-blue-500/10'
          : 'border-slate-700 bg-slate-800/50 hover:bg-slate-700/40 hover:border-slate-600'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-slate-200 truncate flex-1">
          {humanizeName(template.name)}
        </h4>
        <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium border ${colors.bg} ${colors.text} ${colors.border}`}>
          {template.category}
        </span>
      </div>
      <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
        {template.description}
      </p>
    </button>
  );
}

// --- PromptPreview ---

function PromptPreview({
  name,
  onUse,
}: {
  name: string | null;
  onUse?: (content: string) => void;
}) {
  const { data, isLoading } = usePromptTemplateContent(name);

  if (!name) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-sm">
        Select a prompt to preview
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-4 space-y-3">
        <div className="h-6 bg-slate-800 rounded animate-pulse w-48" />
        <div className="h-4 bg-slate-800 rounded animate-pulse w-full" />
        <div className="h-4 bg-slate-800 rounded animate-pulse w-3/4" />
        <div className="h-4 bg-slate-800 rounded animate-pulse w-5/6" />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
        <div>
          <h3 className="text-sm font-medium text-slate-200">{humanizeName(data.name)}</h3>
          {data.category && (
            <span className={`text-[10px] ${getCategoryColors(data.category).text}`}>
              {data.category}
            </span>
          )}
        </div>
        {onUse && (
          <Button
            onClick={() => onUse(data.content)}
            size="sm"
            className="h-7 text-xs"
          >
            Use this prompt
          </Button>
        )}
      </div>
      <div className="flex-1 overflow-auto p-4">
        <pre className="text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
          {data.content}
        </pre>
      </div>
    </div>
  );
}

// --- PromptLibraryCore (shared logic) ---

interface PromptLibraryCoreProps {
  onUse?: (content: string) => void;
  compact?: boolean;
}

function PromptLibraryCore({ onUse, compact = false }: PromptLibraryCoreProps) {
  const { data: templatesData, isLoading } = usePromptTemplates();
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);

  const categories = useMemo(() => {
    if (!templatesData?.templates) return [];
    const cats = new Set(templatesData.templates.map(t => t.category));
    return Array.from(cats).sort();
  }, [templatesData]);

  const filtered = useMemo(() => {
    if (!templatesData?.templates) return [];
    return templatesData.templates.filter(t => {
      if (selectedCategory && t.category !== selectedCategory) return false;
      if (search) {
        const q = search.toLowerCase();
        return t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q);
      }
      return true;
    });
  }, [templatesData, search, selectedCategory]);

  // Compact mode: show preview INSTEAD of list when a prompt is selected
  if (compact && selectedPrompt) {
    return (
      <div className="flex flex-col h-full">
        <div className="p-3 border-b border-slate-700">
          <button
            onClick={() => setSelectedPrompt(null)}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            <ArrowLeft size={12} />
            Back to library
          </button>
        </div>
        <div className="flex-1 min-h-0">
          <PromptPreview name={selectedPrompt} onUse={onUse} />
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${compact ? 'flex-col h-full' : 'gap-0 h-[calc(100vh-12rem)]'}`}>
      {/* Left: search + category pills + cards list */}
      <div className={`flex flex-col ${compact ? 'flex-1 min-h-0' : 'w-[340px] border-r border-slate-700'}`}>
        {/* Search */}
        <div className="p-3 border-b border-slate-700">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search prompts..."
              className="w-full bg-slate-900 border border-slate-700 rounded-md pl-8 pr-3 py-1.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* Category pills */}
        <div className="flex flex-wrap gap-1.5 p-3 border-b border-slate-700">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-2 py-1 rounded-full text-[11px] font-medium transition-colors ${
              !selectedCategory
                ? 'bg-blue-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            All
          </button>
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
              className={`px-2 py-1 rounded-full text-[11px] font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Cards list */}
        <div className="flex-1 overflow-auto p-3 space-y-2">
          {isLoading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-16 bg-slate-800 rounded-lg animate-pulse" />
            ))
          ) : filtered.length === 0 ? (
            <div className="text-center py-8 text-sm text-slate-500">
              No prompts found.
            </div>
          ) : (
            filtered.map(t => (
              <PromptCard
                key={t.name}
                template={t}
                isSelected={selectedPrompt === t.name}
                onSelect={() => setSelectedPrompt(t.name)}
              />
            ))
          )}
        </div>
      </div>

      {/* Right: preview (only in non-compact / page mode) */}
      {!compact && (
        <div className="flex-1 min-w-0">
          <PromptPreview name={selectedPrompt} onUse={onUse} />
        </div>
      )}
    </div>
  );
}

// --- PromptLibraryPanel (slide-over for Editor) ---

export function PromptLibraryPanel({
  open,
  onClose,
  onUse,
}: {
  open: boolean;
  onClose: () => void;
  onUse: (content: string) => void;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      {/* Panel */}
      <div className="relative w-[400px] h-full bg-slate-900 border-l border-slate-700 shadow-2xl flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <BookOpen size={16} className="text-blue-400" />
            <h2 className="text-sm font-medium text-slate-200">Prompt Library</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 min-h-0">
          <PromptLibraryCore
            compact
            onUse={(content) => {
              onUse(content);
              onClose();
            }}
          />
        </div>
      </div>
    </div>
  );
}

// --- NewPromptForm ---

const ALL_CATEGORIES = ['Business', 'Content', 'Data', 'Development', 'Education', 'General', 'Legal', 'Support', 'Workflow'];

const CATEGORY_PREFIX: Record<string, string> = {
  Business: 'biz', Content: 'cnt', Data: 'dat', Development: 'dev',
  Education: 'edu', General: 'gen', Legal: 'leg', Support: 'sup', Workflow: 'wf',
};

const NAME_PATTERN = /^[a-z0-9][a-z0-9-]*$/;

function NewPromptForm({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('');
  const [category, setCategory] = useState('General');
  const [content, setContent] = useState('');
  const createPrompt = useCreatePromptTemplate();

  const nameValid = name.trim() === '' || NAME_PATTERN.test(name.trim());
  const prefix = CATEGORY_PREFIX[category] || 'gen';

  const handleNameChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''));
  }, []);

  const handleSubmit = () => {
    if (!name.trim() || !content.trim() || !nameValid) return;
    createPrompt.mutate(
      { name: name.trim(), category, content },
      { onSuccess: () => onClose() },
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-slate-900 border border-slate-700 rounded-lg shadow-2xl w-[560px] max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
          <h2 className="text-sm font-medium text-slate-200">New Prompt</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X size={16} />
          </button>
        </div>
        <div className="p-4 space-y-4 flex-1 overflow-auto">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Name</label>
            <input
              type="text"
              value={name}
              onChange={handleNameChange}
              placeholder="e.g. my-custom-reviewer"
              className={`w-full bg-slate-800 border rounded-md px-3 py-1.5 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none ${
                !nameValid ? 'border-red-500 focus:border-red-500' : 'border-slate-700 focus:border-blue-500'
              }`}
            />
            {name.trim() && nameValid && (
              <p className="text-[11px] text-slate-500 mt-1">
                Will be saved as <span className="text-slate-400 font-mono">{prefix}-{name.trim()}</span>
              </p>
            )}
            {!nameValid && (
              <p className="text-[11px] text-red-400 mt-1">
                Only lowercase letters, digits, and hyphens. Must start with a letter or digit.
              </p>
            )}
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-1.5 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
            >
              {ALL_CATEGORIES.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Content</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Write your prompt in markdown..."
              rows={12}
              className="w-full bg-slate-800 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500 font-mono resize-none"
            />
          </div>
          {createPrompt.error && (
            <div className="rounded-md bg-red-900/30 border border-red-700/50 p-2 text-xs text-red-300">
              {createPrompt.error.message}
            </div>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-slate-700">
          <Button variant="outline" size="sm" onClick={onClose} className="h-8 text-xs">
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={!name.trim() || !nameValid || !content.trim() || createPrompt.isPending}
            className="h-8 text-xs"
          >
            {createPrompt.isPending ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- PromptLibraryPage (standalone /prompts page) ---

export default function PromptLibrary() {
  const [showNewForm, setShowNewForm] = useState(false);

  return (
    <PageShell className="max-w-6xl">
      <Breadcrumb
        items={[{ label: 'Build' }, { label: 'Prompt Library' }]}
        className="mb-4"
      />
      <div className="flex items-center justify-between">
        <PageHeader title="Prompt Library" />
        <Button
          onClick={() => setShowNewForm(true)}
          size="sm"
          className="h-8 text-xs"
        >
          <Plus size={14} className="mr-1.5" />
          New Prompt
        </Button>
      </div>
      <div className="mt-6 border border-slate-700 rounded-lg overflow-hidden">
        <PromptLibraryCore />
      </div>
      {showNewForm && <NewPromptForm onClose={() => setShowNewForm(false)} />}
    </PageShell>
  );
}
