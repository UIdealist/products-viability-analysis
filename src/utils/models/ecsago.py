import numpy as np
from sklearn.metrics.pairwise import cosine_distances
from sklearn.cluster import KMeans
import warnings

class ECSAGO:
    def __init__(self, n_clusters=8, max_iter=100, num_agents=30, chaos_map='logistic', 
                 convergence_threshold=1e-6, random_state=None):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.num_agents = num_agents
        self.chaos_map = chaos_map
        self.convergence_threshold = convergence_threshold
        self.random_state = random_state
        
        if random_state is not None:
            np.random.seed(random_state)
            
        self.centroids = None
        self.labels_ = None
        self.inertia_ = None
        self.n_iter_ = 0
        
    def _logistic_map(self, x, r=3.99):
        return r * x * (1 - x)
    
    def _tent_map(self, x, a=0.5):
        if x < a:
            return x / a
        else:
            return (1 - x) / (1 - a)
    
    def _sine_map(self, x, a=2.3):
        return a * np.sin(np.pi * x) / 4
    
    def _get_chaos_value(self, iteration, agent_idx):
        if self.chaos_map == 'logistic':
            return self._logistic_map((iteration + agent_idx) / (self.max_iter + self.num_agents))
        elif self.chaos_map == 'tent':
            return self._tent_map((iteration + agent_idx) / (self.max_iter + self.num_agents))
        elif self.chaos_map == 'sine':
            return self._sine_map((iteration + agent_idx) / (self.max_iter + self.num_agents))
        else:
            return np.random.random()
    
    def _calculate_fitness(self, centroids, data):
        distances = cosine_distances(data, centroids)
        labels = np.argmin(distances, axis=1)
        inertia = 0
        for i in range(self.n_clusters):
            cluster_data = data[labels == i]
            if len(cluster_data) > 0:
                cluster_distances = cosine_distances(cluster_data, centroids[i:i+1])
                inertia += np.sum(cluster_distances)
        return inertia, labels
    
    def _update_agent_position(self, agent_pos, other_agents, iteration, data_bounds):
        c = 2 * np.exp(-((4 * iteration) / self.max_iter)**2)
        temp_position = np.zeros_like(agent_pos)
        
        for j, other_pos in enumerate(other_agents):
            distance = np.linalg.norm(other_pos - agent_pos)
            if distance > 0:
                s_ij = (other_pos - agent_pos) * np.exp(-distance) * (distance / (distance + 1e-10))
                temp_position += s_ij
        
        chaos_factor = self._get_chaos_value(iteration, 0)
        new_position = c * temp_position + chaos_factor * np.random.uniform(-1, 1, agent_pos.shape)
        
        new_position = np.clip(new_position, data_bounds[0], data_bounds[1])
        return new_position
    
    def fit(self, X):
        if X.ndim != 2:
            raise ValueError("Input data must be 2D array")
        
        n_samples, n_features = X.shape
        
        data_min = np.min(X, axis=0)
        data_max = np.max(X, axis=0)
        data_bounds = (data_min, data_max)
        
        agents = np.random.uniform(data_min, data_max, (self.num_agents, self.n_clusters, n_features))
        
        best_centroids = None
        best_inertia = float('inf')
        best_labels = None
        
        for iteration in range(self.max_iter):
            for agent_idx in range(self.num_agents):
                current_centroids = agents[agent_idx]
                inertia, labels = self._calculate_fitness(current_centroids, X)
                
                if inertia < best_inertia:
                    best_inertia = inertia
                    best_centroids = current_centroids.copy()
                    best_labels = labels.copy()
                
                other_agents = np.concatenate([agents[:agent_idx], agents[agent_idx+1:]])
                other_agents = other_agents.reshape(-1, n_features)
                
                for centroid_idx in range(self.n_clusters):
                    centroid_pos = current_centroids[centroid_idx]
                    other_centroids = other_agents
                    
                    new_centroid = self._update_agent_position(
                        centroid_pos, other_centroids, iteration, data_bounds
                    )
                    agents[agent_idx, centroid_idx] = new_centroid
            
            if iteration > 0 and abs(best_inertia - prev_inertia) < self.convergence_threshold:
                break
                
            prev_inertia = best_inertia
        
        self.centroids = best_centroids
        self.labels_ = best_labels
        self.inertia_ = best_inertia
        self.n_iter_ = iteration + 1
        
        return self
    
    def predict(self, X):
        if self.centroids is None:
            raise ValueError("Model must be fitted before prediction")
        
        distances = cosine_distances(X, self.centroids)
        return np.argmin(distances, axis=1)
    
    def fit_predict(self, X):
        return self.fit(X).labels_
    
    def get_params(self, deep=True):
        return {
            'n_clusters': self.n_clusters,
            'max_iter': self.max_iter,
            'num_agents': self.num_agents,
            'chaos_map': self.chaos_map,
            'convergence_threshold': self.convergence_threshold,
            'random_state': self.random_state
        }
    
    def set_params(self, **params):
        for param, value in params.items():
            setattr(self, param, value)
        return self
