const dinkyApp = {
    data() {
        return {
            recurring: [
                {
                    title: "👑",
                    repeat: 1,
                    people:
                        [
                            ["estelle.jpg"],
                            ["josephine.jpg"]
                        ]
                },
                {
                    title: "🍽",
                    repeat: 1,
                    people:
                        [
                            ["josephine.jpg", "dasha.jpg"],
                            ["nastia.jpg", "estelle.jpg"]
                        ]
                },
            ],
            countdowns: [
                {image: "caspar.jpg", title: "🎂", date: "03/09/2023"},
                {image: "josephine.jpg", title: "🎂", date: "03/21/2023"},
                {image: "jessica.jpg", title: "🎂", date: "01/31/2023"},
                {image: "natasha.jpg", title: "🎂", date: "02/19/2023"},
                {image: "estelle.jpg", title: "🎂", date: "03/04/2023"},
                {image: "nastia.jpg", title: "🎂", date: "02/12/2023"},
                {image: "dasha.jpg", title: "🎂", date: "07/13/2022"},

                {image: "", title: "🇸🇪", date: "7/30/2022"},
                {image: "", title: "🎈", date: "7/03/2022"},
                {image: "", title: "🇪🇸", date: "7/12/2022"},
                {image: "", title: "👩🏾‍🏫", date: "8/22/2022"},

                // Seasons
                {image: "", title: "🍁", date: "9/23/2022"},
                {image: "", title: "❄️", date: "12/21/2022"},
                {image: "", title: "🌸️", date: "3/20/2023"},

                // Public holidays
                {image: "", title: "🎄", date: "12/24/2022"},


            ]
        }
    },
    methods: {
        calculate_days_remaining: function(date) {
            today=new Date();
            // today.setDate(today.getDate()-1)
            var date = new Date(date)
            var difference_in_time = date.getTime() - today.getTime();
            var difference_in_days = Math.ceil(difference_in_time / (1000 * 3600 * 24));
            return difference_in_days
        },
        get_sorted_countdowns: function() {
            let countdowns = this.countdowns.filter(c => {
                return this.calculate_days_remaining(c.date) >= 0
            })
            return countdowns.sort(sort_by_dates)
        },
        get_recurring: function(people) {
            var people_count = people.length
            var days_into_year = daysIntoYear(new Date())
            todays_index = days_into_year % people_count
            console.log(people_count + " people found")
            console.log("Days into year " + days_into_year)
            console.debug("Today's index = " + todays_index)
            return people[todays_index]
        }
    }
}

function sort_by_dates(a, b) {
    a_date = new Date(a.date)
    b_date = new Date(b.date)
    if ( a_date > b_date ) {
        return 1
    }
    if (a_date < b_date) {
        return -1
    }
    return 0
}

function daysIntoYear(date){
    return (Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) - Date.UTC(date.getFullYear(), 0, 0))
        / 24 / 60 / 60 / 1000;
}
    
Vue.createApp(dinkyApp).mount('#app')