const dinkyApp = {
    data() {
        return {
            message: "DinkyDash",
            recurring: [
                {
                    title: "👑",
                    slots:
                        [ "josephine.jpg", "estelle.jpg" ]
                },
                {
                    title: "🛏",
                    slots:
                        [ "caspar.jpg", "jessica.jpg"  ]
                },
            ],
            countdowns: [
                {image: "caspar.jpg", title: "🎂", date: "03/09/2022"},
                {image: "josephine.jpg", title: "🎂", date: "03/21/2022"},
                {image: "jessica.jpg", title: "🎂", date: "01/22/2022"},
                {image: "natasha.jpg", title: "🎂", date: "02/19/2022"},
                {image: "estelle.jpg", title: "🎂", date: "03/04/2022"},
                {image: "", title: "🎄", date: "12/24/2021"},
                {image: "", title: "🎅", date: "12/06/2021"},
                {image: "estelle.jpg", title: "🎈", date: "12/19/2021"},
                {image: "", title: "🍬️", date: "12/19/2021"},
                {image: "", title: "🧸🪁", date: "12/18/2021"},
                {image: "", title: "👯‍♀️", date: "12/09/2021"},
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
            return this.countdowns.sort(sort_by_dates)
        },
        get_recurring: function(slots) {
            var slots_count = slots.length
            var days_into_year = daysIntoYear(new Date())
            todays_index = days_into_year % slots_count
            console.log(slots_count + " slots found")
            console.log("Days into year " + days_into_year)
            console.debug("Today's index = " + todays_index)
            return slots[todays_index]
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