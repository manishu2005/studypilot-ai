const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options={}){
    const response = await fetch(
        `${API_BASE}${path}`, {...options, headers:{
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...(options.headers || {}),
        }}
    )

    if (!response.ok){
        let message = `Request failed (${response.status})`;
        try {
            const data = await response.json();
            message = data.detail || message;
        } catch (error) {
            console.error("Could not parse error response:", error);
        }
        throw new Error(message);
        
    }
    return response.json();
}

export function getDashboard(){
    return request("/api/learner/dashboard");
}

export function getMastery() {
return request("/api/learner/mastery");
}

export function getRevision(topic) {
return request(`/api/learner/revision/${encodeURIComponent(topic)}`);
}

export function getTopicProgress(topic) {
return request(`/api/learner/progress/${encodeURIComponent(topic)}`);
}