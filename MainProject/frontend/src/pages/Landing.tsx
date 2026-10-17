import { Navigate } from "react-router-dom";
import { Logo } from "../components/AppShell";
import { DemoBanner } from "../components/DemoBanner";
import { ButtonLink, Pill } from "../components/ui";
import { useAuth } from "../lib/auth";

export default function Landing() {
  const { user } = useAuth();
  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen">
      <DemoBanner compact />
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 lg:px-6">
        <Logo />
        <nav className="flex items-center gap-2">
          <ButtonLink to="/login" variant="ghost">Sign in</ButtonLink>
          <ButtonLink to="/signup">Create account</ButtonLink>
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-8 lg:grid-cols-[1.05fr_1fr] lg:px-6 lg:pt-16">
          <div>
            <h1 className="text-[2.6rem] font-extrabold leading-[1.05] sm:text-6xl">
              Practise with an interviewer that listens to your answers.
            </h1>
            <p className="mt-6 max-w-xl text-lg text-muted">
              Every follow-up is chosen from what you just said. Get it right and the questions get harder;
              stumble and it steps back to find the gap. Each session remembers where you struggled, so the next one starts there.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink to="/signup" className="px-6 py-3 text-base">Start practising</ButtonLink>
              <ButtonLink to="/login" variant="secondary" className="px-6 py-3 text-base">I have an account</ButtonLink>
            </div>
            <p className="mt-4 text-sm text-muted">Java, Python, data, web, ML and custom roles · English or हिन्दी · text or voice</p>
          </div>

          {/* The characteristic moment: one answer changing the next question. */}
          <figure className="rounded-2xl border border-line bg-surface p-5 shadow-[0_1px_0_var(--line)] sm:p-7" aria-label="Example of an adaptive follow-up">
            <p className="text-sm font-bold text-muted">Interviewer</p>
            <p className="mt-1 font-display text-2xl font-bold leading-snug">What is polymorphism in Java?</p>

            <div className="ml-auto mt-5 max-w-[85%] rounded-xl rounded-tr-sm bg-surface-2 px-4 py-3">
              <p className="text-sm font-bold text-muted">You</p>
              <p>It means one thing can have many forms.</p>
            </div>

            <div className="mt-4 flex flex-wrap gap-2" aria-label="Evaluation">
              <Pill tone="good">Definition is correct</Pill>
              <Pill tone="warn">No example</Pill>
              <Pill tone="warn">Partial understanding</Pill>
            </div>

            <div className="mt-5 border-l-[3px] border-accent pl-4">
              <p className="text-sm font-bold text-accent">Follow-up · same topic</p>
              <p className="mt-1 font-display text-xl font-bold leading-snug">
                Can you explain compile-time and runtime polymorphism with a simple Java example?
              </p>
              <p className="mt-2 text-sm text-muted">Why this question: the definition was right, but it didn't show how polymorphism works.</p>
            </div>
          </figure>
        </section>

        <section className="border-y border-line bg-surface">
          <div className="mx-auto max-w-6xl px-4 py-14 lg:px-6">
            <h2 className="text-3xl font-extrabold">What happens after every answer</h2>
            <ol className="mt-8 grid gap-8 md:grid-cols-3">
              {[
                ["Evaluate", "Correctness, relevance, depth and clarity are scored separately, so a confident tone is never mistaken for knowing the material."],
                ["Decide", "Follow up on what's missing, step back with a simpler question, raise the difficulty with a real scenario, or move on. Never more than two follow-ups on one topic."],
                ["Remember", "Topic mastery is saved to your profile. Weak topics are scheduled first next time; strong ones get harder questions."],
              ].map(([t, b], i) => (
                <li key={t} className="flex gap-4">
                  <span className="font-display text-4xl font-extrabold text-accent" aria-hidden>{i + 1}</span>
                  <div>
                    <h3 className="text-xl font-bold">{t}</h3>
                    <p className="mt-1 text-muted">{b}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="mx-auto grid max-w-6xl gap-10 px-4 py-14 md:grid-cols-2 lg:px-6">
          <div>
            <h2 className="text-2xl font-extrabold">Set up like the real thing</h2>
            <ul className="mt-4 space-y-2 text-muted">
              <li>Technical, HR, project-based, coding or mixed interviews</li>
              <li>Fixed or adaptive difficulty, 10 to 45 minutes, your choice of question count</li>
              <li>Upload a resume or job description and questions follow your skills</li>
              <li>Ask for a hint, hear the question again, or skip; all of it is recorded honestly</li>
              <li>Speak your answers with the microphone, or type them</li>
            </ul>
          </div>
          <div>
            <h2 className="text-2xl font-extrabold">Honest by design</h2>
            <ul className="mt-4 space-y-2 text-muted">
              <li>Scores are labelled as AI estimates, kept apart from what's measured directly</li>
              <li>No promises about real interviews; practice is practice</li>
              <li>Your interviews are never used to train a model unless you opt in</li>
              <li>Export or delete your data at any time</li>
            </ul>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-muted lg:px-6">
          <span>Interview Room, an adaptive interview practice tool</span>
          <ButtonLink to="/signup" variant="secondary">Create a free account</ButtonLink>
        </div>
      </footer>
    </div>
  );
}
