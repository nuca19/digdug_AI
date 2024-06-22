from dis import dis
import math
import asyncio
import getpass
import json
import os
import heapq
import websockets
import heapq

last_moves = [] #list of last 5 moves

#heuristic function 
def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) # Manhattan distance

#normal approach to nearest enemy
def direction_to_enemy(digdug_pos, enemy): 
    enemy_pos = enemy.get('pos') 
    enemy_dir = enemy.get('dir')
    
    if (enemy_dir == 0 or enemy_dir == 2):
        if digdug_pos[0] != enemy_pos[0]:
            return 'd' if digdug_pos[0] < enemy_pos[0] else 'a'
        else:
            return 's' if digdug_pos[1] < enemy_pos[1] else 'w'

    
    elif (enemy_dir == 1 or enemy_dir == 3):
        if digdug_pos[1] != enemy_pos[1]:
            return 's' if digdug_pos[1] < enemy_pos[1] else 'w'
        else:
            return 'd' if digdug_pos[0] < enemy_pos[0] else 'a'
        
    return 'A'

        
# a* algorithm
def a_star(start, goal, open_loc): #checks if there is a path through open locations to the nearest enemy
    frontier = []
    heapq.heappush(frontier, (0, start))
    came_from = {start: None}
    cost_so_far = {start: 0}

    while frontier:
        _, current = heapq.heappop(frontier)

        if current == goal:
            break

        for next in [(current[0] + dx, current[1] + dy) for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)] if (current[0] + dx, current[1] + dy) in open_loc]:
            new_cost = cost_so_far[current] + 1
            if next not in cost_so_far or new_cost < cost_so_far[next]:
                cost_so_far[next] = new_cost
                priority = new_cost + heuristic(next, goal)
                heapq.heappush(frontier, (priority, next))
                came_from[next] = current

    return came_from, cost_so_far

#takes the nodes from a* and returns the path
def reconstruct_path(came_from, start, goal):
    current = goal
    path = []
    while current != start:
        path.append(current)
        current = came_from[current]
    path.append(start) 
    path.reverse()  
    return path



async def agent_loop(server_address="localhost:8000", agent_name="108810"):
    async with websockets.connect(f"ws://{server_address}/player") as websocket:
        # Receive information about static game properties
        await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))

        while True:
            try:
                state = json.loads(await websocket.recv())  # receive game update, this must be called timely or your game will get out of sync with the server
                
                digdug_pos = state.get('digdug') # get digdug position
                enemies = state.get('enemies', []) # get enemies
                level = state.get('level')
                #initialmap = state.get('map')

                if not enemies:
                    continue
                
            #nearest enemy variables
                nearest_enemy = min(enemies, key=lambda enemy: heuristic(digdug_pos, enemy.get('pos')))
                nearest_enemy_name = nearest_enemy.get('name')
                nearest_enemy_pos = nearest_enemy.get('pos')
                nearest_enemy_dir = nearest_enemy.get('dir')
                distance_to_nearest_enemy = heuristic(digdug_pos, nearest_enemy_pos)

                rocks = state.get('rocks',[])                
                if not rocks:
                    continue
                
            #rock variables
                nearest_rock = min(rocks, key=lambda rock: heuristic(digdug_pos, rock.get('pos')))
                nearest_rock_pos = nearest_rock.get('pos')
                under_rock_pos = [nearest_rock_pos[0], nearest_rock_pos[1]+1]
                distance_to_nearest_rock = heuristic(digdug_pos, nearest_rock_pos)
                distance_to_under_rock = heuristic(digdug_pos, under_rock_pos)


            #1st iteration
                if last_moves == [] and level == 1:
                    next_key = 'None'
                    counter = 0
                    open_loc = []
                    openloc_path = False
                    traverse_closestloc = False
                    levelcounter = level
                    last_two_positions = [] #for fygar

                
            #every level change
                if levelcounter != level:
                    open_loc.clear() #clear open locations
                    levelcounter = level
    

            #update open locations
                #pos variables in tuple format
                t_digdug_pos = (digdug_pos[0], digdug_pos[1])
                t_nearest_enemy_pos = (nearest_enemy_pos[0], nearest_enemy_pos[1])

                #add digdug position to open locations
                if t_digdug_pos not in open_loc:
                    open_loc.append(t_digdug_pos)
                
                #add enemy positions to open locations
                for enemy in enemies:
                    if enemy.get('name') == "Pooka" and enemy.get('traverse') == True: #skip if pooka is traversing
                        continue
                    t_enemy_pos = (enemy.get('pos')[0], enemy.get('pos')[1])
                    if t_enemy_pos not in open_loc:
                        open_loc.append(t_enemy_pos)
            

            
            #a* algorithm calls
                #pooka case
                if nearest_enemy_name == "Pooka" and nearest_enemy.get('traverse') == True and t_nearest_enemy_pos not in open_loc:#if pooka is traversing
                    # Find the closest open location to the pooka traversing
                    min_distance = float('inf')
                    closest_open_loc = None
                    for location in open_loc:
                        distance = abs(nearest_enemy_pos[0] - location[0]) + abs(nearest_enemy_pos[1] - location[1])  # Manhattan distance
                        if distance < min_distance:
                            min_distance = distance
                            closest_open_loc = location

                    #a* call to closest open location
                    came_from, cost_so_far = a_star(t_digdug_pos, closest_open_loc, open_loc)
                    traverse_closestloc = True #flag to indicate that a* was called to the closest open location
                    
                else:
                    #check if theres a path to fygar (only need the flag value)
                    if nearest_enemy_name == "Fygar":
                        came_from_fygar, cost_so_far = a_star(t_digdug_pos, t_nearest_enemy_pos, open_loc)
                        came_from = came_from_fygar #avoid errors
                        if t_nearest_enemy_pos in came_from_fygar:
                            openloc_path = True

                    #normal a* call to nearest enemy(pooka)
                    else:
                        came_from, cost_so_far = a_star(t_digdug_pos, t_nearest_enemy_pos, open_loc)
            
                    

                
    #CHOOSE NEXT MOVE (KEY)
                        
        #BASE CASES - lowest priority
                #attack the enemy if in range
                if distance_to_nearest_enemy <= 3:
                    key = 'A'

                # check if a path through only open locations was found to the enemy
                elif t_nearest_enemy_pos in came_from and nearest_enemy_name == "Pooka" :
                    path = reconstruct_path(came_from, t_digdug_pos, t_nearest_enemy_pos)
                    next_pos = path[1] if len(path) > 1 else path[0] #get next position in path
                    if next_pos[0] > digdug_pos[0]:
                        key = 'd'
                    elif next_pos[0] < digdug_pos[0]:
                        key = 'a'
                    elif next_pos[1] > digdug_pos[1]:
                        key = 's'
                    elif next_pos[1] < digdug_pos[1]:
                        key = 'w'
                    openloc_path = True
                
                #check if a path through only open locations was found to the closest open location
                elif traverse_closestloc and nearest_enemy_name == "Pooka": #when pooka is traversing
                    if closest_open_loc in came_from:
                        path = reconstruct_path(came_from, t_digdug_pos, closest_open_loc)
                        next_pos = path[1] if len(path) > 1 else path[0]
                        if next_pos[0] > digdug_pos[0]:
                            key = 'd'
                        elif next_pos[0] < digdug_pos[0]:
                            key = 'a'
                        elif next_pos[1] > digdug_pos[1]:
                            key = 's'
                        elif next_pos[1] < digdug_pos[1]:
                            key = 'w'
                        openloc_path = True

                #normal approach to nearest enemy
                else:
                    key = direction_to_enemy(digdug_pos, nearest_enemy)
        
                    

        #OTHER ALGORITHMS - higher priority
            #rock avoidance algorithm 
                if len(last_moves)>0 and next_key != 'None':
                    key = next_key
                    next_key = 'None'
                    counter-=1

                #avoid rock if in the way    
                elif distance_to_nearest_rock <= 1 and  distance_to_nearest_enemy>3 and counter%2 == 0: #dont do 2x in a row
                    if nearest_rock_pos[1] == digdug_pos[1]:
                        if nearest_enemy_pos[0] > digdug_pos[0]:
                            key = 'w'
                            next_key = 'd'
                        elif nearest_enemy_pos[0] < digdug_pos[0]:
                            key = 'w'
                            next_key = 'a'
                    elif nearest_rock_pos[0] == digdug_pos[0] :
                        if nearest_enemy_pos[1] > digdug_pos[1] and nearest_enemy_pos[0] < digdug_pos[0]:
                            key = 'a'
                            next_key = 's'
                        elif nearest_enemy_pos[1] > digdug_pos[1] and nearest_enemy_pos[0] >= digdug_pos[0]:
                            key = 'd'
                            next_key = 's'
                
                #prevent from going under the rock (probably needs higher priority)
                if distance_to_under_rock <= 1 and distance_to_nearest_enemy>=1:
                    if (key == 'd') and under_rock_pos[1] == digdug_pos[1] and under_rock_pos[0] == digdug_pos[0]+1 and nearest_enemy_pos[0]> digdug_pos[0]:
                        key = 's'
                        if nearest_enemy_pos[1] == digdug_pos[1] and counter%2 == 0:
                            next_key = 'd'
                    elif (key == 'a') and under_rock_pos[1] == digdug_pos[1] and under_rock_pos[0] == digdug_pos[0]-1 and nearest_enemy_pos[0]< digdug_pos[0]:
                        key = 's'
                        if nearest_enemy_pos[1] == digdug_pos[1] and counter%2 == 0:
                            next_key = 'a'
                    elif (key == 'w') and under_rock_pos[0] == digdug_pos[0]:
                        key = 'd'

                #rare case - cant reach enemy when enemy stuck with rock
                distance_between_enemy_rock = heuristic(nearest_enemy_pos, nearest_rock_pos)
                if distance_between_enemy_rock <= 1 and not openloc_path and last_moves == ['A','A','A','A','A','A']:
                    key = direction_to_enemy(digdug_pos, nearest_enemy)



            #pooka traverse case 
                if nearest_enemy_name == "Pooka" and nearest_enemy.get('traverse') == True:
                    #avoid enemy
                    if distance_to_nearest_enemy <= 2:
                        if digdug_pos[0] == nearest_enemy_pos[0]:
                            key = 'w' if digdug_pos[1] < nearest_enemy_pos[1] else 's'
                        elif digdug_pos[1] == nearest_enemy_pos[1]:
                            key = 'a' if digdug_pos[0] < nearest_enemy_pos[0] else 'd'  
                        elif digdug_pos[0] < nearest_enemy_pos[0]:
                            key = 'a'
                        elif digdug_pos[0] > nearest_enemy_pos[0]:
                            key = 'd'

                    #only move towards if open path available
                    elif not openloc_path:
                        key = 'A'

                            

            #avoid enemys if in wrong direction to kill - highest priority
                if distance_to_nearest_enemy <= 1 and len(last_moves) > 0:
                    if 'd' and 'A' in last_moves and (nearest_enemy_dir == 0 or nearest_enemy_dir == 2) and nearest_enemy_pos[0] == digdug_pos[0]:
                        if nearest_enemy_pos[0] == 0: #left of screen case
                            key = 'd'
                        else:
                            key = 'a'
                    elif 'a' and 'A' in last_moves and (nearest_enemy_dir == 0 or nearest_enemy_dir == 2) and nearest_enemy_pos[0] == digdug_pos[0]:
                        key = 'd'
                    elif 's' and 'A' in last_moves and (nearest_enemy_dir == 1 or nearest_enemy_dir == 3) and nearest_enemy_pos[1] == digdug_pos[1]:
                        if nearest_enemy_pos[1] == 0: #top of screen case    
                            key = 's'
                        else:
                            key = 'w'
                    elif 'w' and 'A' in last_moves and (nearest_enemy_dir == 1 or nearest_enemy_dir == 3) and nearest_enemy_pos[1] == digdug_pos[1]:
                        key = 's'
                    elif 's' and 'A' in last_moves and (nearest_enemy_dir == 0 or nearest_enemy_dir == 2) and nearest_enemy_pos[0] == digdug_pos[0]:
                        key = 'a'
                    elif 'w' and 'A' in last_moves and (nearest_enemy_dir == 0 or nearest_enemy_dir == 2) and nearest_enemy_pos[0] == digdug_pos[0]:
                        key = 'a'
                    #rare cases
                    elif last_moves == ['d','d','d','d','d','d'] and (nearest_enemy_dir == 1 or nearest_enemy_dir == 3) and nearest_enemy_pos[1] == digdug_pos[1]:
                        key = 'w'
                    elif last_moves == ['a','a','a','a','a','a'] and (nearest_enemy_dir == 1 or nearest_enemy_dir == 3) and nearest_enemy_pos[1] == digdug_pos[1]:
                        key = 'w'
                    elif last_moves == ['s','s','s','s','s','s'] and (nearest_enemy_dir == 0 or nearest_enemy_dir == 2) and nearest_enemy_pos[0] == digdug_pos[0]:
                        key = 'd'
                    elif last_moves == ['w','w','w','w','w','w'] and (nearest_enemy_dir == 0 or nearest_enemy_dir == 2) and nearest_enemy_pos[0] == digdug_pos[0]:
                        key = 'd'
                
            #avoid fygar fire
                #change position if fygar is in the same row and facing digdug
                if nearest_enemy_name == "Fygar" and openloc_path and digdug_pos[1] == nearest_enemy_pos[1] and distance_to_nearest_enemy <= 6:
                    if nearest_enemy_dir == 3 and digdug_pos[0] < nearest_enemy_pos[0]:
                        if nearest_enemy_pos[1] == 0: #top of screen case
                            key = "s"
                        else:
                            key = "w"
                    elif nearest_enemy_dir == 1 and digdug_pos[0] > nearest_enemy_pos[0]:
                        if nearest_enemy_pos[1] == 0: #top of screen 
                            key = "s"
                        else:
                            key = "w"
                    
                #hold position if fygar is above or below digdug
                if nearest_enemy_name == "Fygar" and openloc_path and distance_to_nearest_enemy <= 8:
                    if key == 's' and nearest_enemy_dir == 3 and nearest_enemy_pos[1] == digdug_pos[1]+1  and nearest_enemy_pos[0] > digdug_pos[0]:
                        key = 'A'
                    elif key == 's' and nearest_enemy_dir == 1 and nearest_enemy_pos[1] == digdug_pos[1]+1  and nearest_enemy_pos[0] < digdug_pos[0]:
                        key = 'A'
                    elif key == 'w' and nearest_enemy_dir == 3 and nearest_enemy_pos[1] == digdug_pos[1]-1  and nearest_enemy_pos[0] > digdug_pos[0]:
                        key = 'A'
                    elif key == 'w' and nearest_enemy_dir == 1 and nearest_enemy_pos[1] == digdug_pos[1]-1  and nearest_enemy_pos[0] < digdug_pos[0]:
                        key = 'A'



            #fygar after lvl 7 cases 
                if level >= 7 and nearest_enemy_name == "Fygar":
                    if last_moves == ['A','A','A','A','A','A'] and nearest_enemy_pos in last_two_positions and distance_to_nearest_enemy <= 2:  
                        if nearest_enemy_dir == 0 or nearest_enemy_dir == 2 and nearest_enemy_pos[1]> digdug_pos[1]:
                            key = 'w'
                        elif nearest_enemy_dir == 0 or nearest_enemy_dir == 2 and nearest_enemy_pos[1]< digdug_pos[1]:
                            key = 's'

                    if last_moves[5] == 's' and nearest_enemy_pos[1] == digdug_pos[1] and distance_to_nearest_enemy <= 4:
                        if nearest_enemy_pos[0]> digdug_pos[0]:
                            key = 'a'
                        else:
                            key = 'd'

                    if distance_to_nearest_enemy <= 2:
                        last_two_positions.append(nearest_enemy_pos)
                        if len(last_two_positions) > 2:
                            last_two_positions.pop(0)  # Keep only the last two positions                    
            
            

            #update variables
                #update last moves
                if len(last_moves) >= 6:
                    last_moves.pop(0) #remove oldest move
                last_moves.append(key) #add new move
                
                counter+=1
                if counter%5 == 0: #breaks rocks algorithm rare loop
                    next_key = 'None'

                openloc_path = False
                traverse_closestloc = False
                
                await websocket.send(
                            json.dumps({"cmd": "key", "key": key})
                        )  # send key command to server - you must implement this send in the AI agent
                
            except websockets.exceptions.ConnectionClosedOK:
                print("Server has cleanly disconnected us")
                return



# DO NOT CHANGE THE LINES BELLOW
# You can change the default values using the command line, example:
# $ NAME='arrumador' python3 client.py
loop = asyncio.get_event_loop()
SERVER = os.environ.get("SERVER", "localhost")
PORT = os.environ.get("PORT", "8000")
NAME = os.environ.get("NAME", getpass.getuser())
loop.run_until_complete(agent_loop(f"{SERVER}:{PORT}", NAME))
