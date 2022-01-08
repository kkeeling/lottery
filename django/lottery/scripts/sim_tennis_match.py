import datetime
import numpy as np
import pandas as pd
import math

from random import random

from django.db.models import Q, Sum

from tennis.models import Player, Match


def run():
    def getBigPointProb(server):
        if server==p1:
            return p1_big_point
        elif server==p2:
            return p2_big_point
        else:
            print("Error")
            
    def isBigPoint(server_points, returner_points, tiebreak):
        #server_next_point = server_points+1
        server_next_point = server_points
        #print(server_next_point)
        if tiebreak==False:
            if server_next_point >= 3 and (server_next_point - returner_points) >= 1:
                # print("game point")
                return True
        else:
            if server_next_point >= 6 and abs(server_next_point - returner_points) >= 1:
                # print("set point")
                return True

    def getScore(pointsServer, pointsReturner, server_games, returner_games, completed_sets, tiebreaker):
        in_game = ['15', '30', '40']
        extra = ['D', 'A']
        
        display_server='0'
        display_returner='0'
        
        if tiebreaker==False:
            if pointsServer==0:
                display_server='0'
            elif pointsServer>0 and pointsServer<4:
                display_server=in_game[pointsServer-1]
            elif pointsServer>=4:
                #clean_pointsServer = pointsServer-4
                display_server = 'D'

            if pointsReturner==0:
                display_returner='0'
            elif pointsReturner>0 and pointsReturner<4:
                display_returner=in_game[pointsReturner-1]
            elif pointsReturner>=4:
                #clean_pointsReturner = pointsReturner-4
                display_returner = 'D'
            
            if (pointsServer>=4 and pointsReturner<4) or (pointsServer<4 and pointsReturner>=4):
                display_server='D'
                display_returner='D'

            if display_server=='D' and display_server=='D':
                if pointsServer>pointsReturner:
                    display_server='A'
                elif pointsReturner>pointsServer:
                    display_returner='A'

            if (display_server=='A' and display_returner=='A') or (display_server=='40' and display_returner=='40'):
                display_server = 'D'
                display_returner = 'D'
            if (display_server=='A' and display_returner=='40'):
                display_server = 'A'
                display_returner = 'D'
            if (display_server=='40' and display_returner=='A'):
                display_server = 'D'
                display_returner = 'A'
        else:
            display_server = str(pointsServer)
            display_returner = str(pointsReturner)
        
        if len(completed_sets)==0:
            print(display_server+"-"+display_returner+"|"+"["+str(server_games)+"-"+str(returner_games)+"]")
        else:
            completed = ""
            for sets in completed_sets:
                completed = completed+" "+str(sets[0])+":"+str(sets[1])
            print(display_server+"-"+display_returner+"|"+str(completed)+"["+str(server_games)+":"+str(returner_games)+"]")

    def player_serve(server, returner, server_prob, returner_prob, gamesMatch, S, server_points_match, returner_points_match, server_games, returner_games, server_pointsGame, returner_pointsGame, completed_sets):
        if isBigPoint(server_pointsGame, returner_pointsGame, False):
            server_prob = getBigPointProb(server)
        if random() < server_prob:
            print(server+" ", end = "")
            getScore(server_pointsGame, returner_pointsGame, server_games, returner_games, completed_sets, False)
            server_pointsGame += 1
            server_points_match += 1

            if server == p1 and random() < p1_ace:
                print(f'{p1} ACES!!!')
            elif server == p2 and random() < p2_ace:
                print(f'{p2} ACES!!!')
        else:
            print(server+" ", end = "")
            getScore(server_pointsGame, returner_pointsGame, server_games, returner_games, completed_sets, False)
            returner_pointsGame += 1
            returner_points_match += 1
        if max(server_pointsGame, returner_pointsGame) >= 4 and abs(server_pointsGame - returner_pointsGame) > 1:
            # print("\t", server + ":", str(server_pointsGame) + ",", returner + ":", returner_pointsGame, end = "")
            if server_pointsGame > returner_pointsGame:
                server_games += 1
                print()
            else:
                returner_games += 1
                print(" -- " + returner, "broke")
            gamesMatch += 1
            return server_games, returner_games, gamesMatch, S, server_points_match, returner_points_match, server_pointsGame, returner_pointsGame

        return server_games, returner_games, gamesMatch, S, server_points_match, returner_points_match, server_pointsGame, returner_pointsGame

    def simulateSet(a, b, gamesMatch, S, pointsMatch1, pointsMatch2, completed_sets):
        S += 1
        gamesSet1 = 0
        gamesSet2 = 0
        while (max(gamesSet1, gamesSet2) < 6 or abs(gamesSet1 - gamesSet2) < 2) and gamesSet1 + gamesSet2 < 12: #Conditions to play another Game in this Set
            pointsGame1 = 0
            pointsGame2 = 0
            #player 1 serves
            while gamesMatch % 2 == 0:
                gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2, pointsGame1, pointsGame2 = player_serve(p1, p2, a, b, gamesMatch, S, pointsMatch1, pointsMatch2, gamesSet1, gamesSet2, pointsGame1, pointsGame2, completed_sets)
            pointsGame1 = 0
            pointsGame2 = 0
            #player 2 serves, but we also incorporate in logic to end the set
            while gamesMatch % 2 == 1 and (max(gamesSet1, gamesSet2) < 6 or abs(gamesSet1 - gamesSet2) < 2) and gamesSet1 + gamesSet2 < 12:
                gamesSet2, gamesSet1, gamesMatch, S, pointsMatch2, pointsMatch1, pointsGame2, pointsGame1 = player_serve(p2, p1, b, a, gamesMatch, S, pointsMatch2, pointsMatch1, gamesSet2, gamesSet1, pointsGame2, pointsGame1, completed_sets)
        #at 6 games all we go to a tie breaker
        if gamesSet1 == 6 and gamesSet2 == 6:
            print("Set", S, "is 6-6 and going to a Tiebreaker.")
        
        return gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2

    def simulateTiebreaker(player1, player2, a, b, gamesMatch, pointsMatch1, pointsMatch2, completed_sets):
        pointsTie1, pointsTie2 = 0, 0           
        while max(pointsTie1, pointsTie2) < 7 or abs(pointsTie1 - pointsTie2) < 2:
            #player 1 will server first
            if gamesMatch % 2 == 0:
                while (pointsTie1 + pointsTie2) % 4 == 0 or (pointsTie1 + pointsTie2) % 4 == 3:
                    server_prob = a
                    if isBigPoint(pointsTie1, pointsTie2, True):
                        server_prob=getBigPointProb(player1)
                    if random() < server_prob:
                        print(player1+" ", end = "")
                        getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                        pointsTie1 += 1
                        pointsMatch1 += 1

                        if random() < p1_ace:
                            print(f'{p1} ACES!!!')
                    else:
                        getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                        pointsTie2 += 1
                        pointsMatch2 += 1
                    if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
                        print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
                        gamesMatch += 1
                        break 
                while (max(pointsTie1, pointsTie2) < 7 or abs(pointsTie1 - pointsTie2) < 2) and ((pointsTie1 + pointsTie2) % 4 == 1 or (pointsTie1 + pointsTie2) % 4 == 2): # Conditions to continue Tiebreaker (race to 7, win by 2) and Player 2 serves (points 4N+1 and 4N+2)
                    server_prob = b
                    if isBigPoint(pointsTie2, pointsTie1, True):
                        server_prob=getBigPointProb(player2)
                    if random() < server_prob:
                        #print(player2+" ", end = "")
                        getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                        pointsTie2 += 1
                        pointsMatch2 += 1

                        if random() < p2_ace:
                            print(f'{p2} ACES!!!')
                    else:
                        getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                        pointsTie1 += 1
                        pointsMatch1 += 1
                    if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
                        # print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
                        break
            
            #player 2 will server first
            if gamesMatch % 2 == 1:
                while (pointsTie1 + pointsTie2) % 4 == 1 or (pointsTie1 + pointsTie2) % 4 == 2:
                    server_prob =  a
                    if isBigPoint(pointsTie1, pointsTie2, True):
                        server_prob=getBigPointProb(player1)
                    if random() < server_prob:
                        #print(player1+" ", end = "")
                        getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                        pointsTie1 += 1
                        pointsMatch1 += 1
                    else:
                        getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                        pointsTie2 += 1
                        pointsMatch2 += 1
                    # if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
                    #     print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
                    #     break 
                while (max(pointsTie2, pointsTie1) < 7 or abs(pointsTie1 - pointsTie2) < 2) and ((pointsTie1 + pointsTie2) % 4 == 0 or (pointsTie1 + pointsTie2) % 4 == 3): # Conditions to continue Tiebreaker (race to 7, win by 2) and Player 2 serves (points 4N and 4N+3)
                    server_prob =  b
                    if isBigPoint(pointsTie2, pointsTie1, True):
                        server_prob=getBigPointProb(player2)
                    if random() < server_prob:
                        #print(player2+" ", end = "")
                        getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                        pointsTie2 += 1
                        pointsMatch2 += 1
                    else:
                        getScore(pointsTie1, pointsTie2, 6, 6, completed_sets, True)
                        pointsTie1 += 1
                        pointsMatch1 += 1
                    # if max(pointsTie1, pointsTie2) >= 7 and abs(pointsTie1 - pointsTie2) > 1:
                    #     print("\t", p1 + ":", str(pointsTie1) + ",", p2 + ":", pointsTie2)
                    #     break                             
        gamesMatch += 1
        return pointsTie1, pointsTie2, gamesMatch, pointsMatch1, pointsMatch2

    def printSetMatchSummary(p1, p2, gamesSet1, gamesSet2, S, pointsTie1, pointsTie2, setsMatch1, setsMatch2):
        if gamesSet1 > gamesSet2:
            setsMatch1 += 1
            # print(p1.upper(), "wins Set", str(S) + ":", gamesSet1, "games to", str(gamesSet2) + ".")
        elif gamesSet2 > gamesSet1:
            setsMatch2 += 1
            # print(p2.upper(), "wins Set", str(S) + ":", gamesSet2, "games to", str(gamesSet1) + ".")
        elif gamesSet1 == gamesSet2:
            if pointsTie1 > pointsTie2:
                setsMatch1 += 1
                # print(p1.upper(), "wins Set", str(S) + ": 7 games to 6 (" + str(pointsTie1) + "-" + str(pointsTie2) + ").")
            else:
                setsMatch2 += 1
                # print(p2.upper(), "wins Set", str(S) + ": 7 games to 6 (" + str(pointsTie2) + "-" + str(pointsTie1) + ").")
        # print("After", S, "Sets:", p1, str(setsMatch1) + ",", p2, str(setsMatch2) + ".\n")   
        return setsMatch1, setsMatch2

    def pointsMatchSummary(p1, p2, setsMatch1, setsMatch2, pointsMatch1, pointsMatch2):
        if setsMatch1 == sets_to_win:
            print(p1.upper(), "(" + str(a) + ")", "beat", p2, "(" + str(b) + ") by", setsMatch1, "Sets to", str(setsMatch2) + ".")
            return p1
        else:
            print(p2.upper(), "(" + str(b) + ")", "beat", p1, "(" + str(a) + ") by", setsMatch2, "Sets to", str(setsMatch1) + ".")
            return p2

    last_52_weeks = Match.objects.filter(
        winner__tour='atp',
        surface='Hard',
        tourney_date__gte=datetime.date.today() - datetime.timedelta(weeks=52),
        tourney_date__lte=datetime.date.today()
    )
    w_serve_points_data = last_52_weeks.exclude(
        Q(Q(w_svpt=None) | Q(w_1stWon=None) | Q(w_2ndWon=None))
    ).aggregate(
        num_points=Sum('w_svpt'),
        num_1stWon=Sum('w_1stWon'),
        num_2ndWon=Sum('w_2ndWon')
    )
    l_serve_points_data = last_52_weeks.exclude(
           Q(Q(l_svpt=None) | Q(l_1stWon=None) | Q(l_2ndWon=None))
    ).aggregate(
        num_points=Sum('l_svpt'),
        num_1stWon=Sum('l_1stWon'),
        num_2ndWon=Sum('l_2ndWon')
    )
    avg_serve_point_rate = round((w_serve_points_data.get('num_1stWon') + w_serve_points_data.get('num_2ndWon') + l_serve_points_data.get('num_1stWon') + l_serve_points_data.get('num_2ndWon')) / (w_serve_points_data.get('num_points') + l_serve_points_data.get('num_points')), 4)
    avg_return_point_rate = 1 - avg_serve_point_rate

    #initialize player one and two
    #a is ps1 and b is ps2
    #p1_big_point and p2_big_point are the probability
    #of p1 and p2 winning on a big point, respectively
    player_1 = Player.objects.get(id=36658)
    player_2 = Player.objects.get(id=4544)
    p1 = player_1.full_name
    p2 = player_2.full_name

    a_prime = player_1.get_return_points_rate()
    b_prime = player_2.get_return_points_rate()
    a_diff = ((a_prime/avg_return_point_rate) - 1) * .15
    b_diff = ((b_prime/avg_return_point_rate) - 1) * .15

    a = player_1.get_serve_points_rate() * (1 + (b_diff * -1))
    b = player_2.get_serve_points_rate() * (1 + (a_diff * -1))

    p1_big_point = a
    p2_big_point = b
    p1_ace = player_1.get_ace_pct()
    p2_ace = player_2.get_ace_pct()
    p1_df = player_1.get_df_pct()
    p2_df = player_2.get_df_pct()
    p1_break = player_1.get_return_points_rate()
    p2_break = player_2.get_return_points_rate()


    best_of = 3
    sets_to_win = math.ceil(best_of/2)
    p1_wins = 0
    p2_wins = 0

    for _ in range(0, 1):
        completed_sets = []
        S = 0
        gamesMatch = 0

        #in all subscripted variables
        #the subscript refers to the player
        #for example, setsMatch1 is sets won by player1 and
        #setsMatch2 is sets won by player2
        pointsMatch1, pointsMatch2 = 0, 0
        setsMatch1, setsMatch2 = 0, 0
        pointsTie1, pointsTie2 = 0, 0
        pointsGame1, pointsGame2 = 0, 0
        breaks1, breaks2 = 0, 0
        aces1, aces2 = 0, 0
        doubles1, doubles2 = 0, 0

        while S < best_of and max(setsMatch1, setsMatch2) < sets_to_win:
            gamesSet1, gamesSet2, gamesMatch, S, pointsMatch1, pointsMatch2 = simulateSet(a, b, gamesMatch, S, 
                                                                                        pointsMatch1, pointsMatch2, 
                                                                                        completed_sets)
            # print()
            if gamesSet1 == 6 and gamesSet2 == 6:
                pointsTie1, pointsTie2, gamesMatch, pointsMatch1, pointsMatch2 = simulateTiebreaker(p1, p2, a, b, 
                                                                                                    gamesMatch, pointsMatch1, 
                                                                                                    pointsMatch2, 
                                                                                                    completed_sets)
            
            setsMatch1, setsMatch2 = printSetMatchSummary(p1, p2, gamesSet1, gamesSet2, 
                                                        S, pointsTie1, pointsTie2, 
                                                        setsMatch1, setsMatch2)
            
            if gamesSet1 == 6 and gamesSet2 == 6:
                if pointsTie1 > pointsTie2:
                    completed_sets.append([gamesSet1+1, gamesSet2])
                else:
                    completed_sets.append([gamesSet1, gamesSet2+1])
            else:
                completed_sets.append([gamesSet1, gamesSet2])

        winner = pointsMatchSummary(p1, p2, setsMatch1, setsMatch2, pointsMatch1, pointsMatch2)
        if winner == p1:
            p1_wins += 1
        else:
            p2_wins += 1

    print(f'{p1} wins {p1_wins} times out of 1000.')

    