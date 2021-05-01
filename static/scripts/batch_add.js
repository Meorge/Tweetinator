var numberOfTweets = 0;
var modal = null;

var basicTab = null;
var advancedTab = null;

var isoDateFormat = ""
var prettyDateFormat = "MMMM D, YYYY [at] hh:mm A";
var separator = "\n"

function updateSeparator(text) {
    if (text == "") {
        separator = "\n"
    } else {
        separator = "\n" + text + "\n"
    }
    updateBasicAddTweetButton(document.getElementById("simpleBatchTweetText").value);
}
function updateBasicAddTweetButton(text) {
    numberOfTweets = text.split(separator).filter((a) => a != "").length;
    if (text == "") { numberOfTweets = 0; }

    document.getElementById("batchSimplePreviewButton").innerHTML = `Preview ${numberOfTweets} Tweet${numberOfTweets == 1 ? '' : 's'} to Queue`;
    document.getElementById("batchSimplePreviewButton").disabled = numberOfTweets == 0;

    updateUpcomingDates();
}

function updateUpcomingDates() {
    let startDate = dayjs(document.getElementById("tweetInitialPostTime").value);
    let numberOfMinutes = document.getElementById("tweetIntervalPostTime").value;

    let maxNumberOfDatesToCalculate = 5;
    let numberOfDatesToCalculate = Math.min(maxNumberOfDatesToCalculate, numberOfTweets);

    let dateStrings = [];

    for (let i = 0; i < numberOfDatesToCalculate; i++) {
        let nextDate = dayjs(startDate).add(numberOfMinutes * i, 'minute');
        dateStrings.push(nextDate.format(prettyDateFormat));
    }

    let finalDateString = dayjs(startDate).add(numberOfMinutes * (numberOfTweets - 1), 'minute');

    let listedDates = "";
    document.getElementById("upcomingTweetTimes").textContent = '';
    for (let i = 0; i < dateStrings.length; i++) {
        let listItem = document.createElement('li');
        listItem.innerHTML = dateStrings[i];

        document.getElementById("upcomingTweetTimes").appendChild(listItem);
    }

    if (numberOfTweets > maxNumberOfDatesToCalculate) {
        let etcItem = document.createElement('li');
        etcItem.innerHTML = "etc";
        document.getElementById("upcomingTweetTimes").appendChild(etcItem);
    }

    document.getElementById("lastTweetTime").textContent = finalDateString.format(prettyDateFormat);
    
}

function parseBasicTweets() {
    console.log("Parse basic tweets");
    let inputTweets = document.getElementById("simpleBatchTweetText").value.split(separator).filter((a) => a != "");

    // inputTweets.map((input) => input.replace(/\\n/g, /\n/g));
    let shuffleTweets = document.getElementById("shuffleTweets").checked;

    if (shuffleTweets) {
        inputTweets = _.shuffle(inputTweets);
    }

    let listOfTweetObjects = [];
    let startDate = dayjs(document.getElementById("tweetInitialPostTime").value);
    let numberOfMinutes = document.getElementById("tweetIntervalPostTime").value;

    for (let i = 0; i < inputTweets.length; i++) {
        let thisTweetDate = dayjs(startDate).add(numberOfMinutes * i, 'minute');
        let tweetObject = {
            "text": inputTweets[i],
            "postDate": thisTweetDate
        }

        listOfTweetObjects.push(tweetObject);
    }

    // Populate the preview table
    let modalTweetTable = document.getElementById("modalTweetTable");

    // First, clear the current contents
    modalTweetTable.innerText = "";

    listOfTweetObjects.forEach((element) => {
        // Create a new row for each item
        let thisRow = document.createElement('tr');

        // Create a cell for the Tweet text
        let thisRowText = document.createElement('td');
        let thisRowDate = document.createElement('td');

        // Populate the cells
        thisRowText.textContent = element.text;
        thisRowDate.textContent = element.postDate.format(prettyDateFormat);

        thisRow.appendChild(thisRowText);
        thisRow.appendChild(thisRowDate);

        modalTweetTable.appendChild(thisRow);
    });


    // Determine the content of the confirmation button
    let confirmButton = document.getElementById("batchSimpleConfirmButton")
    let confirmButtonContent = document.getElementById("batchSimpleConfirmButtonContent");
    confirmButtonContent.innerText = `Add ${numberOfTweets} Tweet${numberOfTweets == 1 ? '' : 's'} to Queue`;
    confirmButton.onclick = () => uploadTweets(listOfTweetObjects);

    // Hide the error modal
    let errorAlert = document.getElementById("batchSimpleConfirmModalError");
    errorAlert.style = "display: none;";

    let errorMessage = document.getElementById("batchSimpleConfirmModalErrorMessage");
    errorMessage.textContent = "This message should not appear";

    modal.show();

    return false;
}

function lockModal() {
    // Disable the close button
    let closeButton = document.getElementById("batchSimpleCloseButton");
    closeButton.disabled = true;

    // Disable the submit button
    let confirmButton = document.getElementById("batchSimpleConfirmButton");
    confirmButton.disabled = true;

    // Disable the cancel button
    let cancelButton = document.getElementById("batchSimpleCancelButton");
    cancelButton.disabled = true;

    // Show thinking spinner
    let spinner = document.getElementById("batchSimpleConfirmSpinner");
    spinner.style = "";
}

function unlockModal() {
    // Disable the close button
    let closeButton = document.getElementById("batchSimpleCloseButton");
    closeButton.disabled = false;

    // Disable the submit button
    let confirmButton = document.getElementById("batchSimpleConfirmButton");
    confirmButton.disabled = false;

    // Disable the cancel button
    let cancelButton = document.getElementById("batchSimpleCancelButton");
    cancelButton.disabled = false;

    // Show thinking spinner
    let spinner = document.getElementById("batchSimpleConfirmSpinner");
    spinner.style = "display: none;";
}


function uploadTweets(tweets) {
    console.log("upload time!!");
    console.log(tweets);

    let botName = $('#bot_name').data().name;

    let serializedTweets = tweets.map((tweet) => {
        // console.log(`tweet.postDate);
        console.log(`${tweet.postDate}`);
        console.log(tweet.postDate.utc().format("YYYY-MM-DDTHH:mm"));
        return {
            "text": tweet.text,
            "post_at": tweet.postDate.utc().format("YYYY-MM-DDTHH:mm")
        };
    });

    console.log(serializedTweets);

    $.ajax({
        url: `/api/${botName}/batch_add`,
        data: JSON.stringify(serializedTweets),
        success: function(response) {
            console.log(response);
            if (response.response == "success") {
                window.location.href = `/${botName}/upcoming`;
            } else {
                unlockModal();

                let errorAlert = document.getElementById("batchSimpleConfirmModalError");
                errorAlert.style = "";

                let errorMessage = document.getElementById("batchSimpleConfirmModalErrorMessage");
                errorMessage.textContent = response.message;
            }
            
        },
        dataType: "json",
        contentType: "application/json",
        type: "post"
    });

    lockModal();

}

function displayAdvancedError(message) {
    let errorAlert = document.getElementById("batchAdvancedError");
    errorAlert.style = "";

    let errorMessage = document.getElementById("batchAdvancedErrorMessage");
    errorMessage.textContent = message;
}

function parseAdvancedTweets() {
    // Parse what was typed into JSON
    let listOfTweets = [];
    try {
        listOfTweets = JSON.parse(document.getElementById("advancedBatchTweetText").value);
    }
    catch (error) {
        console.log(`Error caught: ${error}`);
        displayAdvancedError(error);
        return;
    }

    // Ensure this is an array of objects
    if (!Array.isArray(listOfTweets)) {
        console.log("Not an array!!");
        displayAdvancedError("Not an array of JSON objects");
        return;
    }

    // We have an array of Tweets
    // Let's make sure they're valid
    for (var i = 0; i < listOfTweets.length; i++) {
        // Ensure text exists
        let thisTweet = listOfTweets[i];
        if (!("text" in thisTweet)) {
            thisTweet.text = "";
        }

        // Ensure post_at exists
        if (!("post_at" in thisTweet)) {
            console.log(`post_at is not in tweet ${i}`);
            displayAdvancedError(`\"post_at\" is not defined in Tweet at index ${i}`);
            return;
        } else {
            // Ensure it's a valid timestamp
            let tryDate = dayjs(thisTweet["post_at"])
            if (!tryDate.isValid()) {
                console.log(`post_at date \"${thisTweet["post_at"]}\" is not a valid date in tweet ${i}`);
                displayAdvancedError(`\"post_at\" is not a valid date in Tweet at index ${i}`);
                return;
            }
        }

        // Ensure dont_reschedule exists
        if (!("dont_reschedule" in thisTweet)) {
            thisTweet.dont_reschedule = false
        }

        // Ensure media exists
        if (!("media" in thisTweet)) {
            thisTweet.media = ["", "", "", ""]
        } else {
            // Ensure media is an array
            if (!Array.isArray(thisTweet["media"])) {
                console.log(`media is not an array in tweet ${i}`);
                displayAdvancedError(`\"media\" is not an array in Tweet at index ${i}`);
                return;
            } else {
                // Ensure media array has four values
                if (thisTweet["media"].length != 4) {
                    console.log(`media array is of length ${thisTweet["media"].length} instead of 4 in tweet ${i}`);
                    displayAdvancedError(`\"media\" does not have 4 elements in Tweet at index ${i}`);
                    return;
                }
            }
        }
    }

    console.log("tweets are ok");

    let botName = $('#bot_name').data().name;

    // Upload them all to the server!
    $.ajax({
        url: `/api/${botName}/batch_add`,
        data: JSON.stringify(listOfTweets),
        success: function(response) {
            console.log(response);
            if (response.response == "success") {
                window.location.href = `/${botName}/upcoming`;
            } else {
                console.log("Error adding Tweets");
                displayAdvancedError(response.message);
            }
        },
        dataType: "json",
        contentType: "application/json",
        type: "post"
    });

}

$(document).ready(function() {
    updateBasicAddTweetButton("");

    $("#simpleBatchForm").submit(parseBasicTweets);

    let defaultDate = dayjs().add(1, 'hour');
    let defaultDateString = defaultDate.format("YYYY-MM-DDTHH:mm");
    document.getElementById("tweetInitialPostTime").value = defaultDateString;

    modal = new bootstrap.Modal(document.getElementById("batchSimpleConfirmModal"), {
        "backdrop": 'static',
        "keyboard": false,
        "focus": true
    });

    modal.hide();

    basicTab = new bootstrap.Tab(document.getElementById("simple-tab"));
    advancedTab = new bootstrap.Tab(document.getElementById("advanced-tab"));

    document.getElementById("simple-tab").addEventListener('click', function(event) {
        console.log("simple got clicked");
        event.preventDefault();
        basicTab.show();
    });

    document.getElementById("advanced-tab").addEventListener('click', function(event) {
        console.log("advanced got clicked");
        event.preventDefault();
        advancedTab.show();
    });

    updateUpcomingDates();

    // Hide advanced error modal by default
    let advErrorAlert = document.getElementById("batchAdvancedError");
    advErrorAlert.style = "display: none;";
});