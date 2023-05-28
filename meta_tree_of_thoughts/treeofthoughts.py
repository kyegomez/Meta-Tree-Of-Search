import os
import time
import json
from openaiModel import OptimizedOpenAILanguageModel
import logging 
import argparse
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional, Set, Tuple, Union

class TreeofThoughts:
    def __init__(self, model, search_algorithm):
        self.model = model
        self.search_algorithm = search_algorithm
        self.tree: Dict[str, Dict[str, float]] = {
            "nodes": {}
        }

    def solve(self, initial_prompt: str, 
              num_thoughts: Optional[int] = 3, 
              max_steps: Optional[int] = 3, 
              max_states: Optional[int] = 5, 
              value_threshold: Optional[float] = 0.5,
              confidence_threshold: Optional[float] = 0.8, 
              max_iterations: Optional[int] = 40, 
              convergence_threshold: Optional[float] = None, 
              convergence_count: Optional[int] = None) -> str:
        start_time = time.time()
        self.file_name = f"logs/tree_of_thoughts_output_{self.search_algorithm}.json"
        try:
            best_thoughts = ""
            if self.search_algorithm == 'BFS':
                result = self.tot_bfs(initial_prompt, num_thoughts, max_steps, max_states, value_threshold)
                if result:
                    self.save_tree_to_json(self.file_name)
                    best_thoughts = result
            elif self.search_algorithm == 'DFS':
                result = self.tot_dfs(initial_prompt, num_thoughts, max_steps, value_threshold, 
                                        confidence_threshold=confidence_threshold, max_iterations=max_iterations, convergence_threshold=convergence_threshold, 
                                        convergence_count=convergence_count)
                if result:
                    self.save_tree_to_json(self.file_name)
                    best_thoughts = result
            if best_thoughts:
                solution = self.model.generate_solution(initial_prompt, best_thoughts)
                if solution:
                    return solution
            else:
                raise ValueError("Invalid search algorithm. Choose 'BFS' or 'DFS'.")
        except KeyboardInterrupt:
            logger.error("Keyboard interrupt detected.")
        except ValueError as e:
            logger.error(f"Error: {e}")
        finally:
            logger.info("Saving the current tree and metrics.")
            self.save_tree_to_json(self.file_name)
    
    def logNewState(self, state, evaluation):
        if not (type(state) == str):
            state = " | ".join(state)
        self.tree["nodes"][state] = evaluation
        self.save_tree_to_json(self.file_name)    
        
    def tot_bfs(self, initial_prompt, num_thoughts, max_steps, max_states, pruning_threshold):
        current_states = [initial_prompt]
        state_values = {}
        for step in range(1, max_steps + 1):
            selected_states = []
            for state in current_states:
                thoughts = self.model.generate_thoughts(state, num_thoughts, initial_prompt)
                evaluated_thoughts = self.model.evaluate_states({thought: 0 for thought in thoughts}, initial_prompt)
                for thought, value in evaluated_thoughts.items():
                    if value >= pruning_threshold:
                        flattened_state = (state, thought)
                        if not (type(state) == str):
                            flattened_state = (*state, thought)
                        selected_states.append(flattened_state)
                        state_values[flattened_state] = value
                        self.logNewState(flattened_state, value)
            if(len(selected_states) >1):
                current_states = selected_states[:max_states]
                
        if (len(current_states) == 1):
            return initial_prompt
        print(current_states, state_values)
        best_state = max(current_states, key=lambda state: state_values[state])
        print(f'best_state: {best_state}')

        return best_state

    def tot_dfs(self, 
                initial_prompt: str, 
                num_thoughts: any,
                max_steps: int,
                value_threshold, 
                pruning_threshold=0.5, 
                confidence_threshold=None, max_iterations=None, convergence_threshold=None, convergence_count=None):
        output = []
        iteration_count = 0
        consecutive_convergence_count = 0
        prev_best_value = None
        file_name = f"logs/tree_of_thoughts_output_{self.search_algorithm}.json"

        def dfs(state, step):
            nonlocal consecutive_convergence_count, prev_best_value, iteration_count, output
            if step > max_steps:
                thought = self.model.generate_thoughts(state, 1, initial_prompt)
                value = self.model.evaluate_states({state}, initial_prompt)[state]
                output.append((thought, value))

                if confidence_threshold is not None and value >= confidence_threshold:
                    return True

                if prev_best_value is not None and convergence_threshold is not None:
                    if abs(value - prev_best_value) < convergence_threshold:
                        consecutive_convergence_count += 1
                    else:
                        consecutive_convergence_count = 0

                prev_best_value = value
                iteration_count += 1

                if (max_iterations is not None and iteration_count >= max_iterations) or (convergence_count is not None and consecutive_convergence_count >= convergence_count):
                    return True

                return False

            for next_state in sorted(self.model.generate_thoughts(state, num_thoughts, initial_prompt)):
                state_value = self.model.evaluate_states({next_state}, initial_prompt)[next_state]
                logger.info(f"State: {next_state}, Value: {state_value}")

                if state_value > value_threshold and (pruning_threshold is None or state_value >= pruning_threshold):
                    if (type(state) == str):
                        child = (state, next_state)
                    else:
                        child = (*state, next_state)

                    if dfs(child, step + 1):
                        return True

            self.save_tree_to_json(file_name)
            return False

        dfs(initial_prompt, 1)
        best_state = max(output, key=lambda x: x[1])
        return best_state[0]

    def save_tree_to_json(self, file_name):
        os.makedirs(os.path.dirname(file_name), exist_ok=True)

        with open(file_name, 'w') as json_file:
            json.dump(self.tree, json_file, indent=4)

    def print_tree(self, 
                   node: str, 
                   depth=0):
        thought = self.tree["metrics"]["thoughts"].get(node, "")
        evaluation = self.tree["metrics"]["evaluations"].get(node, "")

        tree_info = f"{'  ' * depth}Node: {node}, Thought: {thought}, Evaluation: {evaluation}\n"

        for child, parent in self.tree["nodes"].items():
            if parent == node:
                tree_info += self.print_tree(child, depth + 1)
                print(f'tree info: {tree_info}')

        return tree_info



#does not output state after each thought --- idk why -- needs work
class OptimizedTreeofThoughts(TreeofThoughts):
    def solve(self, x, k=None, T=None, b=None, vth=None, timeout=None, confidence_threshold=None, max_iterations=None, convergence_threshold=None, convergence_count=None):
        start_time = time.time()
        print(f'Start time {start_time}')
        if self.search_algorithm == 'BFS':
            while timeout is None or time.time() - start_time < timeout:
                result = self.tot_bfs(x, k, T, b, pruning_threshold=0.5)
                print(f'result in optimized tree of thoughts: {result}')
                if result:
                    return result
        elif self.search_algorithm == 'DFS':
            while timeout is None or time.time() - start_time < timeout:
                result = self.tot_dfs(x, k, T, vth, confidence_threshold=confidence_threshold, max_iterations=max_iterations, convergence_threshold=convergence_threshold, convergence_count=convergence_count)
                if result:
                    return result
        else:
            raise ValueError("Invalid search algorithm. Choose 'BFS' or 'DFS'.")

