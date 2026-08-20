import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthApi } from "../services/api";
import { useAuth } from "../store/auth";

export default function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const setAuth = useAuth((s) => s.setAuth);
  const navigate = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (isRegister) {
        await AuthApi.register(email, username, password, true);
      }
      const { access_token } = await AuthApi.login(email, password);
      setAuth(access_token, username || email);
      navigate("/lobby");
    } catch {
      setError("Login failed — check your credentials.");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card-surface w-full max-w-md p-8">
        <h1 className="text-3xl font-display font-bold text-gold-500 text-center">
          Deals Rummy
        </h1>
        <p className="text-center text-slate-400 mt-1 mb-6">
          {isRegister ? "Create your account" : "Welcome back"}
        </p>
        <form onSubmit={submit} className="space-y-3">
          <input className="input" placeholder="Email" type="email" value={email}
                 onChange={(e) => setEmail(e.target.value)} required />
          {isRegister && (
            <input className="input" placeholder="Username" value={username}
                   onChange={(e) => setUsername(e.target.value)} required />
          )}
          <input className="input" placeholder="Password" type="password" value={password}
                 onChange={(e) => setPassword(e.target.value)} required />
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button className="btn-gold w-full" type="submit">
            {isRegister ? "Register & Play" : "Login"}
          </button>
        </form>
        <button className="mt-4 text-sm text-slate-400 hover:text-gold-400 w-full text-center"
                onClick={() => setIsRegister((v) => !v)}>
          {isRegister ? "Have an account? Login" : "New here? Create an account"}
        </button>
      </div>
    </div>
  );
}
