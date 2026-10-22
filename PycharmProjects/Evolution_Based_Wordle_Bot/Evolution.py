import random

valid_characters = ["-","0","1","2","3","4","5","6","7","8","9","a","b","c","d","e","f","g","h","i","j","k","l","m","n","o","p","q","r","s","t","u","v","w","x","y","z"]

# phase One

def generate_phrase(length):
    phrase = ""
    for i in range(length):
        next_char = random.choice(valid_characters)
        phrase += next_char
    return phrase

def create_first_population(size):
    first_population = []
    for i in range(size):
        first_population.append(generate_phrase(len(Goal_Phrase)))
    return first_population

# Phase Two

def calculate_fitness(candidate, target):
    score = 0
    for i in range(len(candidate)):
        if candidate[i] in target:
            score += 1
        if target[i] == candidate[i]:
            score += 1
    return score

def evaluate_population(population, target):
    scores = []
    for i in range(len(population)):
        scores.append((calculate_fitness(population[i], target)))
    #Sort
    sorted_pairs = sorted(zip(scores, population), reverse=True)
    scores, population = zip(*sorted_pairs)
    scores = list(scores)
    population = list(population)
    return population

# Phrase Three

def select_parents():
    return current_population[5:]

def crossover(parent_a, parent_b):
    # Iterate over both parents character by character simultaneously
    child_chars = [
        char_a if random.random() < 0.5 else char_b
        for char_a, char_b in zip(parent_a, parent_b)
    ]
    return "".join(child_chars)


def mutate(candidate, mutation_rate):
    mutated_candidate = []
    for i in range(len(candidate)):
        if random.random() < mutation_rate / 100:
            mutated_candidate.append(random.choice(valid_characters))
        else:
            mutated_candidate.append(candidate[i])
    return "".join(mutated_candidate)

# Main
try:
    times = []
    while True:
        Goal_Phrase = input("Which phrase would you like to evolve to? \n")
        current_population = create_first_population(20)
        iterations = 0
        last_phrase = ""
        while iterations < 1234567 and current_population[0] != Goal_Phrase:
            iterations += 1
            current_population = evaluate_population(current_population, Goal_Phrase)
            print(current_population)
            parents = current_population[:5]
            current_population = parents
            if parents[0] != last_phrase:
                print("Iteration", iterations , ":", parents[0])
                last_phrase = parents[0]
            for i in range(15):
                parent_a, parent_b = random.sample(parents, 2)
                child = crossover(parent_a, parent_b)
                child = mutate(child, 25)
                current_population.append(child)
        print("Phrase", Goal_Phrase, "took", iterations, "iterations to evolve.")
        times.append(iterations)
except KeyboardInterrupt:
    average_time = sum(times) / len(times)
    print("Average time: ", average_time, len(times))

