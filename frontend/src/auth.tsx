import { ReactNode, createContext, useContext, useEffect, useMemo, useState } from 'react';
import { ClerkProvider, SignInButton, SignedIn, SignedOut, UserButton, useAuth } from '@clerk/clerk-react';
import { setAuthHeadersProvider } from './api';
import {
  DEV_USER_STORAGE_KEY,
  bearerAuthHeaders,
  devAuthHeaders,
  resolveAuthMode,
  sanitizeDevUserId,
} from './authModel';

const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

type DevAuthContextValue = {
  userId: string;
  setUserId: (userId: string) => void;
};

const DevAuthContext = createContext<DevAuthContextValue | null>(null);

export function useDevAuth(): DevAuthContextValue | null {
  return useContext(DevAuthContext);
}

function ClerkTokenBridge({ children }: { children: ReactNode }) {
  const { getToken } = useAuth();

  useEffect(() => {
    setAuthHeadersProvider(async () => bearerAuthHeaders(await getToken()));
  }, [getToken]);

  return <>{children}</>;
}

function DevAuthProvider({ children }: { children: ReactNode }) {
  const [userId, setUserIdState] = useState<string>(() =>
    sanitizeDevUserId(window.localStorage.getItem(DEV_USER_STORAGE_KEY)),
  );

  useEffect(() => {
    window.localStorage.setItem(DEV_USER_STORAGE_KEY, userId);
    setAuthHeadersProvider(async () => devAuthHeaders(userId));
  }, [userId]);

  const value = useMemo(
    () => ({ userId, setUserId: (next: string) => setUserIdState(sanitizeDevUserId(next)) }),
    [userId],
  );

  return <DevAuthContext.Provider value={value}>{children}</DevAuthContext.Provider>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  if (resolveAuthMode(CLERK_PUBLISHABLE_KEY) === 'clerk') {
    return (
      <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY!}>
        <SignedIn>
          <ClerkTokenBridge>{children}</ClerkTokenBridge>
        </SignedIn>
        <SignedOut>
          <div className="auth-signed-out">
            <h1>SimpleTS</h1>
            <p>Sign in to access your workspace.</p>
            <SignInButton mode="modal" />
          </div>
        </SignedOut>
      </ClerkProvider>
    );
  }
  return <DevAuthProvider>{children}</DevAuthProvider>;
}

export function AuthControls() {
  const devAuth = useDevAuth();

  if (devAuth === null) {
    return <UserButton />;
  }

  return (
    <label className="dev-auth-controls">
      Acting as
      <input
        value={devAuth.userId}
        onChange={(event) => devAuth.setUserId(event.target.value)}
        aria-label="Dev user id"
      />
    </label>
  );
}
