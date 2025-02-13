"""This script analyzes chess game data, calculates various statistics (including sums, medians, and averages), 
and generates a final DataFrame with player statistics, sorted by the average gi score in descending order.
"""

from epr_calculator import adjust_mn, optimize_w, calculate_EPR
import pandas as pd
import sys
import os
import glob

def combine_csv_files(input_dir, output_filename='combined.csv'):
    csv_files = glob.glob(os.path.join(input_dir, '*.csv'))
    combined_df = pd.DataFrame()

    for file in csv_files:
        df = pd.read_csv(file)
        combined_df = pd.concat([combined_df, df], ignore_index=True)

    output_path = os.path.join(input_dir, output_filename)
    combined_df.to_csv(output_path, index=False)
    print(f"Combined CSV created at {output_path}")
    return output_path

# Functions
def read_csv(file_path):
    return pd.read_csv(file_path)

def check_dataframe(df, df_name):
    print(f"Columns in {df_name}: {df.columns}")

def calculate_sum(df, group_col, value_col, prefix):
    sums = df.groupby(group_col).agg({value_col: 'sum'}).reset_index()
    sums.columns = ['Player', f'{prefix}_sum']
    return sums

def calculate_games(df, player_col):
    game_count = df[player_col].value_counts().reset_index()
    game_count.columns = ['Player', f'{player_col}_games']
    return game_count

def calculate_total_games(white_games, black_games):
    total_games = pd.merge(white_games, black_games, on='Player', how='outer').fillna(0)
    total_games['total_game_count'] = total_games['White_games'] + total_games['Black_games']
    return total_games

def calculate_total_moves(df):
    # Summing up the moves made by each player as White and Black
    white_moves = calculate_sum(df, 'White', 'white_move_number', 'white_move')
    black_moves = calculate_sum(df, 'Black', 'black_move_number', 'black_move')
    total_moves = pd.merge(white_moves, black_moves, on='Player', how='outer').fillna(0)
    total_moves['total_moves'] = total_moves['white_move_sum'] + total_moves['black_move_sum']
    return total_moves[['Player', 'total_moves']]

def calculate_statistics(df, value_col):
    stats = df.groupby('Player').agg(median=(value_col, 'median'), 
                                     var=(value_col, 'var'), 
                                     std=(value_col, 'std')).reset_index()
    return stats.rename(columns={'median': f'{value_col}_median', 
                                 'var': f'{value_col}_var', 
                                 'std': f'{value_col}_std'})

def calculate_opponent_elo_sums(df):
    # Assuming the DataFrame df has columns for opponent Elo ratings for each game
    # You might need to adjust this logic based on how your data is structured
    white_opponent_elo_sum = df.groupby('White')['BlackElo'].sum().reset_index().rename(columns={'White': 'Player', 'BlackElo': 'sum_opponent_elo'})
    black_opponent_elo_sum = df.groupby('Black')['WhiteElo'].sum().reset_index().rename(columns={'Black': 'Player', 'WhiteElo': 'sum_opponent_elo'})
    
    # Merge and sum Elo ratings from both white and black perspectives
    opponent_elo_sums = pd.merge(white_opponent_elo_sum, black_opponent_elo_sum, on='Player', how='outer').fillna(0)
    opponent_elo_sums['sum_opponent_elo'] = opponent_elo_sums['sum_opponent_elo_x'] + opponent_elo_sums['sum_opponent_elo_y']
    opponent_elo_sums = opponent_elo_sums[['Player', 'sum_opponent_elo']]
    
    return opponent_elo_sums

def calculate_avg_opponent_elo(opponent_elo_sums, total_games):
    # Merge with total games to calculate average
    merged = pd.merge(opponent_elo_sums, total_games[['Player', 'total_game_count']], on='Player')
    merged['avg_opponent_elo'] = merged['sum_opponent_elo'] / merged['total_game_count']
    return merged[['Player', 'avg_opponent_elo']]

def calculate_average_elo(df):
    # Calculate average Elo when playing as White
    white_elo_avg = df.groupby('White')['WhiteElo'].mean().reset_index().rename(columns={'White': 'Player', 'WhiteElo': 'avg_elo_white'})
    black_elo_avg = df.groupby('Black')['BlackElo'].mean().reset_index().rename(columns={'Black': 'Player', 'BlackElo': 'avg_elo_black'})
    elo_avg = pd.merge(white_elo_avg, black_elo_avg, on='Player', how='outer').fillna(0)
    elo_avg['Elo'] = elo_avg.apply(lambda row: round((row['avg_elo_white'] + row['avg_elo_black']) / 2 if row['avg_elo_white'] > 0 and row['avg_elo_black'] > 0 else max(row['avg_elo_white'], row['avg_elo_black']), 0), axis=1)
    return elo_avg[['Player', 'Elo']]

def calculate_tpr(player_stats):
    threshold_prob = 0.75
    player_stats['w_star'] = player_stats.apply(lambda row: optimize_w(row['Points'], row['total_game_count'], threshold_prob), axis=1)
    player_stats['TPR'] = player_stats.apply(lambda row: round(calculate_EPR(row['w_star'], row['avg_opponent_elo']),0), axis=1)
    return player_stats

def merge_dataframes(dfs, merge_on='Player'):
    merged_df = dfs[0]
    for df in dfs[1:]:
        merged_df = pd.merge(merged_df, df, on=merge_on, how='outer').fillna(0)
    return merged_df

def calculate_averages(player_stats):
    player_stats['avg_gi'] = player_stats['total_gi_sum'] / player_stats['total_game_count']
    player_stats['avg_gi_raw'] = player_stats['total_gi_raw_sum'] / player_stats['total_game_count']
    player_stats['avg_gpl'] = player_stats['total_gpl_sum'] / player_stats['total_game_count']
    player_stats['avg_acpl'] = player_stats['total_acpl_sum'] / player_stats['total_game_count']
    return player_stats

def save_to_csv(df, file_path):
    df.to_csv(file_path, index=False)

# Main Functionality
def main_stats(csv_all_games_path, player_stats_output_dir):
    if not os.path.exists(csv_all_games_path):
        print(f"File not found: {csv_all_games_path}")
        return
    df = read_csv(csv_all_games_path)
    # check_dataframe(df, "Initial DataFrame")

    # Calculating Sums
    white_gi_sum = calculate_sum(df, 'White', 'white_gi', 'white_gi')
    black_gi_sum = calculate_sum(df, 'Black', 'black_gi', 'black_gi')
    white_gi_raw_sum = calculate_sum(df, 'White', 'white_gi_raw', 'white_gi_raw')
    black_gi_raw_sum = calculate_sum(df, 'Black', 'black_gi_raw', 'black_gi_raw')
    white_gpl_sum = calculate_sum(df, 'White', 'white_gpl', 'white_gpl')
    black_gpl_sum = calculate_sum(df, 'Black', 'black_gpl', 'black_gpl')
    white_acpl_sum = calculate_sum(df, 'White', 'white_acpl', 'white_acpl')
    black_acpl_sum = calculate_sum(df, 'Black', 'black_acpl', 'black_acpl')
    # Calculate sum of results for each player (not as White and Black but in total)
    white_result_sum = calculate_sum(df, 'White', 'WhiteResult', 'white_result')  # Calculate white results sum
    black_result_sum = calculate_sum(df, 'Black', 'BlackResult', 'black_result')  # Calculate black results sum

    # Calculating Game Counts
    white_games = calculate_games(df, 'White')
    black_games = calculate_games(df, 'Black')
    total_games = calculate_total_games(white_games, black_games)
    total_moves = calculate_total_moves(df)
    
    combined_df = pd.concat([
        df[['White', 'white_gi', 'white_gi_raw', 'white_gpl', 'white_acpl']].rename(columns={'White': 'Player', 'white_gi': 'gi', 'white_gi_raw': 'gi_raw', 'white_gpl': 'gpl', 'white_acpl': 'acpl'}),
        df[['Black', 'black_gi', 'black_gi_raw', 'black_gpl', 'black_acpl']].rename(columns={'Black': 'Player', 'black_gi': 'gi', 'black_gi_raw': 'gi_raw', 'black_gpl': 'gpl', 'black_acpl': 'acpl'})
    ])

    gi_stats = calculate_statistics(combined_df, 'gi')
    gi_raw_stats = calculate_statistics(combined_df, 'gi_raw')
    gpl_stats = calculate_statistics(combined_df, 'gpl')
    acpl_stats = calculate_statistics(combined_df, 'acpl')

    # Merging DataFrames
    sums = [white_gi_sum, black_gi_sum, white_gi_raw_sum, black_gi_raw_sum, white_gpl_sum, black_gpl_sum, white_acpl_sum, black_acpl_sum, white_result_sum, black_result_sum]  # Add white_result_sum and black_result_sum to the list
    total_sums = merge_dataframes(sums + [total_games, total_moves])
    total_sums['total_gi_sum'] = total_sums['white_gi_sum'] + total_sums['black_gi_sum']
    total_sums['total_gi_raw_sum'] = total_sums['white_gi_raw_sum'] + total_sums['black_gi_raw_sum']
    total_sums['total_gpl_sum'] = total_sums['white_gpl_sum'] + total_sums['black_gpl_sum']
    total_sums['total_acpl_sum'] = total_sums['white_acpl_sum'] + total_sums['black_acpl_sum']
    total_sums['Points'] = total_sums['white_result_sum'] + total_sums['black_result_sum']  # Add Points calculation

    player_stats = merge_dataframes([total_sums, gi_stats, gi_raw_stats, gpl_stats, acpl_stats])

    # Calculating Averages
    player_stats = calculate_averages(player_stats)

    # Calculate sum_opponent_elo and avg_opponent_elo
    opponent_elo_sums = calculate_opponent_elo_sums(df)
    avg_opponent_elo = calculate_avg_opponent_elo(opponent_elo_sums, total_games)

    # Merge avg_opponent_elo with the player_stats DataFrame before calculating TPR
    player_stats = pd.merge(player_stats, avg_opponent_elo, on='Player', how='left')

    # Calculate TPR
    player_stats = calculate_tpr(player_stats)

    # In the main function or the appropriate place in your script, after you have the initial df DataFrame:
    average_elo = calculate_average_elo(df)

    # Merge this Elo information with the player_stats DataFrame
    player_stats = pd.merge(player_stats, average_elo, on='Player', how='left')
    
    # columns_to_include
    columns_to_include = ['Player', 'avg_gi', 'avg_gpl', 'avg_acpl', 'total_game_count', 'Points', 'Elo', 'TPR', 'total_moves', 'White_games', 'Black_games', 'gi_median', 'gpl_median', 'acpl_median', 'gi_std', 'gpl_std', 'acpl_std', 'avg_gi_raw', 'white_gpl_sum', 'black_gpl_sum', 'white_acpl_sum', 'black_acpl_sum', 'white_result_sum', 'black_result_sum', 'total_gpl_sum', 'gi_var', 'gi_raw_median', 'gi_raw_var', 'gi_raw_std', 'gpl_var', 'acpl_var']
    player_stats = player_stats[columns_to_include]

    # Ensure the output directory exists
    if not os.path.exists(player_stats_output_dir):
        os.makedirs(player_stats_output_dir)

    # Define the output CSV file path within the output directory
    output_file_path = os.path.join(player_stats_output_dir, 'player_stats.csv')

    # Sorting and Saving
    player_stats = player_stats.sort_values(by='avg_gi', ascending=False)
    save_to_csv(player_stats, output_file_path)
