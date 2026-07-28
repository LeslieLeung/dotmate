import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { authApi } from "@/lib/api";
import { getToken, setToken } from "@/lib/auth";

export function LoginPage() {
  const [token, setTokenValue] = useState("");
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    authApi
      .status(getToken())
      .then((status) => {
        if (!active) return;
        if (!status.auth_required || status.authenticated) navigate("/", { replace: true });
      })
      .catch(() => {
        if (active) setError("Unable to reach the server");
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => { active = false; };
  }, [navigate]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const value = token.trim();
    if (!value) {
      setError("Admin token is required");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const status = await authApi.status(value);
      if (!status.auth_required || status.authenticated) {
        setToken(value);
        navigate("/", { replace: true });
      } else {
        setError("Invalid admin token");
      }
    } catch {
      setError("Unable to verify the token. Check the server connection.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Dotmate Admin</CardTitle>
          <CardDescription>Enter the admin token configured on the server.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <FieldGroup>
              <Field data-invalid={Boolean(error)}>
                <FieldLabel htmlFor="token">Admin Token</FieldLabel>
                <Input
                  id="token"
                  type="password"
                  placeholder="Enter admin token"
                  value={token}
                  onChange={(event) => {
                    setTokenValue(event.target.value);
                    setError("");
                  }}
                  aria-invalid={Boolean(error)}
                  disabled={checking || submitting}
                  autoFocus
                />
                <FieldError>{error}</FieldError>
              </Field>
              <Button type="submit" className="w-full" disabled={checking || submitting}>
                {(checking || submitting) && <Spinner data-icon="inline-start" />}
                {checking ? "Checking..." : submitting ? "Signing in..." : "Sign In"}
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
