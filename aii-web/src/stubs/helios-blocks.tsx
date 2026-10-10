'use client';
/**
 * Runtime stub for @helios/blocks (private package not available at build time).
 * All components render a placeholder so pages compile and ship without errors.
 * Real components will be wired when @helios/blocks is installed from the private registry.
 */
import type { ReactNode } from 'react';

function Placeholder({ name, ...rest }: { name: string; children?: ReactNode; [k: string]: unknown }) {
  void rest;
  return (
    <div className="rounded-lg border border-dashed border-gray-300 p-4 text-sm text-gray-400 text-center">
      {name}
    </div>
  );
}

export const OAIQAPanel = (props: Record<string, unknown>) =>
  <Placeholder name="OAIQAPanel" {...props} />;

export const OAISummaryCard = (props: Record<string, unknown>) =>
  <Placeholder name="OAISummaryCard" {...props} />;

export const ODocumentReader = (props: Record<string, unknown>) =>
  <Placeholder name="ODocumentReader" {...props} />;

export const OAnnotationLayer = (props: Record<string, unknown>) =>
  <Placeholder name="OAnnotationLayer" {...props} />;

export const OCitationCard = (props: Record<string, unknown>) =>
  <Placeholder name="OCitationCard" {...props} />;

export const OScheduledJobsManager = (props: Record<string, unknown>) =>
  <Placeholder name="OScheduledJobsManager" {...props} />;

export const OSemanticSearch = (props: Record<string, unknown>) =>
  <Placeholder name="OSemanticSearch" {...props} />;

export const OBacklinkPanel = (props: Record<string, unknown>) =>
  <Placeholder name="OBacklinkPanel" {...props} />;

export const ODocumentTree = (props: Record<string, unknown>) =>
  <Placeholder name="ODocumentTree" {...props} />;

// ── Type re-exports (values must exist to avoid module resolution errors) ────
export type Medium = string;
export type SourceType = string;
export type AgentName = string;
export interface Substrate { [k: string]: unknown }
export interface Derivative { [k: string]: unknown }
export interface Note { [k: string]: unknown }
export interface BacklinkItem { [k: string]: unknown }
export interface SearchResult { [k: string]: unknown }
export interface Citation {
  substrate_id: string;
  title?: string;
  fragment_id?: string | null;
  anchor?: string | null;
  deep_link?: string | null;
  [k: string]: unknown;
}
export interface QAResponse {
  answer: string;
  citations: Citation[];
  sources_used?: unknown;
}
export interface OAISummaryCardProps { [k: string]: unknown }
export interface ScheduledJobWithStatus { [k: string]: unknown }
