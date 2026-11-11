import React from "react";
import { SourceChunk } from "../../types";

interface ChunkReviewListProps {
  chunks: SourceChunk[];
  profileId: string;
}

export default function ChunkReviewList({
  chunks,
  profileId,
}: ChunkReviewListProps) {
  const [expanded, setExpanded] = React.useState<Record<string, boolean>>({});

  const toggleExpand = (chunkId: string) => {
    setExpanded((prev) => ({
      ...prev,
      [chunkId]: !prev[chunkId],
    }));
  };

  return (
    <div>
      <h3 className="text-sm font-medium mb-2">Extracted Chunks ({chunks.length})</h3>

      <div className="space-y-3 max-h-80 overflow-y-auto">
        {chunks.map((chunk) => {
          const isExpanded = expanded[chunk.chunk_id] || false;

          return (
            <div
              key={chunk.chunk_id}
              className="border rounded p-3 cursor-pointer hover:border-primary-500 transition-colors"
              onClick={() => toggleExpand(chunk.chunk_id)}
            >
              <div className="flex justify-between items-start">
                <span className="text-xs text-gray-500">
                  {chunk.chunk_type} – {chunk.repo_name || "portfolio"}
                </span>
                <span className="text-xs text-gray-400">{chunk.chunk_id}</span>
              </div>

              {isExpanded && (
                <div className="mt-2 text-xs text-gray-300 whitespace-pre-wrap">
                  {chunk.text.substring(0, 300)}{chunk.text.length > 300 && "..."}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}