#Full Stack Nanodegree Game API Project

1) Instructions for playing the game.
2) Detailed descriptions of each endpoint.
3) Detailed explanation of score keeping.

##Game Description:
Tic-tac-toe is a two-player game where players who take turns marking the spaces
in a 3×3 grid with X and O marks. The player who succeeds in placing three of their
marks in a horizontal, vertical, or diagonal row wins the game.

Scores are recorded when a game ends. The winner and loser are recorded, along with
the number of moves made by the winner and the date in which the score was recorded.

In this API implementation two independent players can compete against each other.

##Endpoints Available:
 - **create_user**
    - Path: 'user/create'
    - Method: POST
    - Parameters: user_name, email
    - Returns: Message confirming creation of the User.
    - Description: Creates a new User. user_name provided must be unique. Will
    raise a ConflictException if a User with that user_name already exists.

 - **new_game**
    - Path: 'game/new'
    - Method: POST
    - Parameters: player1, player2
    - Returns: GameForm with initial game state.
    - Description: Creates a new Game. player1 is mandatory. player2 is optional.
    player1 and player2 provided must be user name of an existing user - will
    raise a NotFoundException if not.

 - **join_game**
    - Path: 'game/{urlsafe_game_key}/join'
    - Method: PUT
    - Parameters: urlsafe_game_key, user_name
    - Returns: GameForm with current game state.
    - Description: Joins the given user to the given game as player 2. Player 2
    must be different than player 1. Throws an exception is a user has already
    joined the game as player 2.
    Will raise a NotFoundException if the User or Game does not exist.

 - **get_game**
    - Path: 'game/{urlsafe_game_key}'
    - Method: GET
    - Parameters: urlsafe_game_key
    - Returns: GameForm with current game state.
    - Description: Returns the current state of a game.
    Will raise a NotFoundException if the Game does not exist.

 - **make_move**
    - Path: 'game/{urlsafe_game_key}/move'
    - Method: PUT
    - Parameters: urlsafe_game_key, user_name, position
    - Returns: GameForm with new game state.
    - Description: Accepts a position on the grid and the player who should
    occupy it. The position is then marked with that user's corresponding
    symbol (X or O). The updated state of the game is then returned.
    A task is created to notify the next player that it is their turn to play.
    If this move causes a game to end, a corresponding Score entity is created.
    Will raise a NotFoundException if the User or Game does not exist.

 - **get_scores**
    - Path: 'scores'
    - Method: GET
    - Parameters: None
    - Returns: ScoreForms, listing all users' scores.
    - Description: Returns all Scores in the database (unordered). Fields
    included are: winner's user name, date game was finished, number of moves
     made by the winner.

 - **get_user_scores**
    - Path: 'scores/user/{user_name}'
    - Method: GET
    - Parameters: user_name
    - Returns: ScoreForms.
    - Description: Returns all Scores recorded by the provided player (unordered).
    Will raise a NotFoundException if the User does not exist.

 - **get_user_games**
    - Path: 'user/games/{user_name}'
    - Method: GET
    - Parameters: user_name
    - Returns: GameForms.
    - Description: Lists all games created by the given user.
    Raises NotFoundException if user does not exist or if user has not created
    any games.

 - **cancel_game**
    - Path: 'game/{urlsafe_game_key}/cancel'
    - Method: PUT
    - Parameters: urlsafe_game_key
    - Returns: Message indicating game has been cancelled.
    - Description: Marks the given game as cancelled.
    Raises BadRequestException if game has already ended by a player winning
    or a tie. Will not raise an exception if the game was previously cancelled
    before there was a winner or a draw.

 - **get_user_rankings**
    - Path: 'user/rankings'
    - Method: GET
    - Parameters: None
    - Returns: RankingForms.
    - Description: Returns all users ranked by their number of wins and average
    number of moves. If two players have won the same number of games, the
    player with the fewer average moves is ranked higher. The list includes
    user name, rank and performance. Rank is a numeric order starting with 1.
    Performance is defined as the ratio of wins over losses.

 - **get_game_history**
    - Path: 'game/{urlsafe_game_key}/history'
    - Method: GET
    - Parameters: urlsafe_game_key
    - Returns: MoveHistoryForms.
    - Description: Returns a move-by-move history of the given game. For each
    move made on the have, user name and position occupied if listed.

##Models:
 - **User**
    - Stores unique user_name and (optional) email address.

 - **Game**
    - Stores unique game states. Associated with User model via KeyProperty.

 - **Score**
    - Records completed games. Associated with User model via KeyProperty.

- **MoveHistory**
    - Records independent user moves. Used by Game model to store game history.

##Forms Included:
 - **GameForm**
    - Representation of a Game's state (urlsafe_key, game_over flag, message,
    player names, next_turn player, current cell position state).
 - **GameForms**
    - Multiple GameForm containers.
 - **PlayersForm**
    - Used to create a new game (player_1, player_2)
 - **MakeMoveForm**
    - Inbound make move form (user_name, position).
 - **ScoreForm**
    - Representation of a completed game's Score (user_name, date, moves).
 - **ScoreForms**
    - Multiple ScoreForm container.
 - **RankingForm**
    - Outbound ranking information (user_name, rank, performance)
 - **RankingForms**
    - Multiple RankingForm containers.
 - **StringMessage**
    - General purpose String container.
