"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth";
import { apiClient } from "@/lib/api-client";

// Mock: Part 3 will replace with GET /api/users/:username
interface PublicProfile {
  username: string;
  display_name: string;
  bio: string;
}

function useMockPublicProfile(username: string): PublicProfile {
  return { username, display_name: username, bio: "（简介待后端接入）" };
}

interface ShareItem {
  token: string;
  note_id: string;
  created_at: string;
  allow_anonymous: boolean;
}

export default function ProfilePage() {
  const params = useParams<{ username: string }>();
  const username = params.username;
  const { user } = useAuthStore();
  const isOwn = user?.username === username;

  return isOwn ? <OwnProfile /> : <PublicProfileView username={username} />;
}

// ── Own profile ──────────────────────────────────────────────────────────────

function OwnProfile() {
  const { user } = useAuthStore();

  const { data: shares, isLoading } = useQuery({
    queryKey: ["shares"],
    queryFn: () => apiClient.get<{ items: ShareItem[]; total: number }>("/api/shares"),
  });

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{user?.username}</h1>
          <p className="text-sm text-[var(--color-muted)]">{user?.email}</p>
        </div>
        <a
          href="/settings"
          className="text-sm px-3 py-1.5 border border-[var(--color-border)] rounded hover:bg-[var(--color-border)]/30"
        >
          编辑资料
        </a>
      </div>

      <div>
        <h2 className="text-base font-medium mb-3">我的公开分享</h2>
        {isLoading && <p className="text-sm text-[var(--color-muted)]">加载中...</p>}
        {!isLoading && shares?.total === 0 && (
          <p className="text-sm text-[var(--color-muted)]">暂无公开分享</p>
        )}
        {shares && shares.total > 0 && (
          <ul className="space-y-2">
            {shares.items.map((s) => (
              <li
                key={s.token}
                className="flex items-center justify-between p-3 border border-[var(--color-border)] rounded text-sm"
              >
                <span className="font-mono text-xs text-[var(--color-muted)]">{s.token}</span>
                <a
                  href={`/share/${s.token}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--color-primary)] hover:underline"
                >
                  查看
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Public (others') profile ─────────────────────────────────────────────────

function PublicProfileView({ username }: { username: string }) {
  // Part 3: replace with useQuery → GET /api/users/:username
  const profile = useMockPublicProfile(username);

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div>
        <h1 className="text-xl font-semibold">{profile.display_name}</h1>
        <p className="text-sm text-[var(--color-muted)]">@{profile.username}</p>
      </div>
      {profile.bio && (
        <p className="text-sm text-[var(--color-muted)]">{profile.bio}</p>
      )}
      <p className="text-xs text-[var(--color-muted)] border-t border-[var(--color-border)] pt-4">
        公开分享将在后续版本显示
      </p>
    </div>
  );
}
