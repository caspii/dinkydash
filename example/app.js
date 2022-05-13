console.log("Hello World")

const dinkyApp = {
    data() {
        return {
            message: "DinkyDash",
            recurring: [
                {
                    title: "🗑",
                    slots:
                        [ "josephine.jpg", "estelle.jpg" ],
                    tooltip: "Who's turn to take out the trash?"
                },
                {
                    title: "🐩",
                    slots:
                        [ "caspar.jpg", "jessica.jpg"  ],
                    tooltip: "Who's turn to walk the poodle?"
                },
            ],
            countdowns: [
                {image: "caspar.jpg", title: "🎂", date: "03/09/2023", tooltip: "How many days till Caspar's birthday?"},
                {image: "jessica.jpg", title: "🎂", date: "01/22/2023", tooltip: "How many days till Jessica's birthday?"},
                {image: "estelle.jpg", title: "🎂", date: "03/04/2023", tooltip: "How many days till Estelle's birthday?"},
                {image: "", title: "🎄", date: "12/25/2023", tooltip: "How many days till Christmas?"},
                {image: "", title: "🎃", date: "10/30/2023", tooltip: "How many days till Halloween?"},
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
    },
    mounted() {
          // Initialise all tooltips
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
        var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl)
        })
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