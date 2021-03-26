function archiveTweet(bot_name, tweet_id, ripple) {
    console.log(`archive the tweet from ${bot_name} with id ${tweet_id} and ripple ${ripple}`);
    $.getJSON(`/api/${bot_name}/tweets/${tweet_id}/archive`, {"ripple": ripple});
    window.location.reload();
}

function unarchiveTweet(bot_name, tweet_id) {
    console.log(`unarchive the tweet from ${bot_name} with id ${tweet_id}`);
    $.getJSON(`/api/${bot_name}/tweets/${tweet_id}/unarchive`);
    window.location.reload();
}

function deleteTweet(bot_name, tweet_id) {
    console.log(`delete the tweet from ${bot_name} with id ${tweet_id} forever!`);
    $.getJSON(`/api/${bot_name}/tweets/${tweet_id}/delete`);
    window.location.reload();
}

function newTweet(bot_name) {
    console.log(`make a new tweet for ${bot_name} and add to queue`)
    $.getJSON(`/api/${bot_name}/new_tweet`, function(response) {
        console.log(response)
        window.location.href = `/${bot_name}/tweets/${response['tweet_id']}/edit`;
    });
}

console.log("Functions loaded");