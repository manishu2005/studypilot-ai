import { useEffect, useState, useCallback } from "react";
import { getDashboard } from "../api";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function Dashboard({onStartQuiz, onStartDiagnostic, onReviewTopic}){
    const[dashboard, setDashboard] = useState(null);
    const[loading, setLoading] = useState(true);
    const[error, setError] = useState("");
    const loadDashboard = useCallback(async ()=>{
        setLoading(true);
        setError("");
        try {
            const response = await fetch(`${API_BASE}/api/learner/dashboard`)
            if(!response.ok){
                throw new Error("Failed to load dashboard");
            }

            const data = await response.json();
            setDashboard(data);
        } catch (error) {
            setError(err.message || "Unable to load your learning profile")
        }finally{
            setLoading(false);
        }
    },[]);

    useEffect(() => {
        loadDashboard();
    }, [loadDashboard])
    

    if (loading){
        return(
            <div>Loading your learning profile</div>
        )
    }

    if(error){
        return (
            <section>
            <h1>Your Learning Dashboard</h1>
            <p role="alert">{error}</p>
            <button onClick={loadDashboard}>Try again</button>
            </section>
        )
    }


    if (!dashboard?.has_data) {
        return (
            <section>
            <h1>Welcome to StudyPilot AI</h1>
            <p>
            Take a diagnostic assessment to establish your initial
            topic mastery and personalize future quizzes.
            </p>
            <button onClick={onStartDiagnostic}>
            Start Diagnostic
            </button>
            </section>
        );
    }

  const recommendation = dashboard.recommendation;


  return(
    <main>
        <header>
            <h1>Your Learning Dashboard</h1>
<p>
Mastery is an estimate based on your recorded assessment
results, not a definitive measurement of knowledge.
</p>
        </header>

        <section aria-labelledby="overall-mastery">
    <h2 id="overall-mastery">Overall estimated mastery</h2>
    <p>
      <strong>
        {Math.round(dashboard.overall_mastery * 100)}%
      </strong>
    </p>
    <p>Status: {dashboard.status}</p>
    <progress
      aria-label="Overall estimated mastery"
      value={dashboard.overall_mastery}
      max="1"
    />
  </section>

  <section aria-labelledby="topic-mastery">
    <h2 id="topic-mastery">Topic mastery</h2>

    {dashboard.topics.map((topic) => (
      <article key={topic.topic}>
        <h3>{topic.topic}</h3>
        <p>
          {Math.round(topic.mastery * 100)}% · {topic.status}
        </p>
        <progress
          aria-label={`${topic.topic} mastery`}
          value={topic.mastery}
          max="1"
        />
        <p>
          Attempts: {topic.attempts} · Correct: {topic.correct} ·
          Incorrect: {topic.incorrect}
        </p>
        <button onClick={() => onReviewTopic(topic.topic)}>
          Review source material
        </button>
        <button
          onClick={() =>
            onStartQuiz(
              topic.topic,
              topic.recommended_difficulty
            )
          }
        >
          Practice this topic
        </button>
      </article>
    ))}
  </section>

  <section aria-labelledby="recommendation">
    <h2 id="recommendation">Recommended next action</h2>
    <p>{recommendation.message}</p>

    {recommendation.topic && (
      <p>
        Topic: <strong>{recommendation.topic}</strong>
        {" · "}
        Difficulty: <strong>{recommendation.difficulty}</strong>
      </p>
    )}

    {recommendation.action === "revision" ? (
      <button
        onClick={() => onReviewTopic(recommendation.topic)}
      >
        Review recommended topic
      </button>
    ) : recommendation.action === "adaptive_quiz" ? (
      <button
        onClick={() =>
          onStartQuiz(
            recommendation.topic,
            recommendation.difficulty
          )
        }
      >
        Start recommended quiz
      </button>
    ) : (
      <button onClick={onStartDiagnostic}>
        Start Diagnostic
      </button>
    )}
  </section>

  {dashboard.weak_topics.length > 0 && (
    <section>
      <h2>Topics to strengthen</h2>
      <ul>
        {dashboard.weak_topics.map((topic) => (
          <li key={topic.topic}>
            {topic.topic} — {Math.round(topic.mastery * 100)}%
          </li>
        ))}
      </ul>
    </section>
  )}

  {dashboard.misconceptions.length > 0 && (
    <section>
      <h2>Recorded misconceptions</h2>
      <ul>
        {dashboard.misconceptions.map((item, index) => (
          <li key={`${item.topic}-${index}`}>
            <strong>{item.topic}:</strong> {item.description}
          </li>
        ))}
      </ul>
    </section>
  )}

  <button onClick={loadDashboard}>
    Refresh learning profile
  </button>

    </main>
  )
}