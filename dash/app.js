const dinkyApp = {
    data() {
        return {
            recurring: [
                {
                    title: "👑",
                    repeat: 1,
                    slots:
                        [ "estelle.jpg", "josephine.jpg" ]
                },
                {
                    title: "🛏",
                    repeat: 1,
                    slots:
                        [ "caspar.jpg", "jessica.jpg" ]
                },
            ],
            countdowns: [
                {image: "caspar.jpg", title: "🎂", date: "03/09/2023"},
                {image: "josephine.jpg", title: "🎂", date: "03/21/2023"},
                {image: "jessica.jpg", title: "🎂", date: "01/31/2023"},
                {image: "natasha.jpg", title: "🎂", date: "02/19/2023"},
                {image: "estelle.jpg", title: "🎂", date: "03/04/2023"},
                {image: "nastia.jpg", title: "🎂", date: "12/02/2023"},
                {image: "dasha.jpg", title: "🎂", date: "13/07/2023"},
                {image: "", title: "🎄", date: "12/24/2022"},
                {image: "", title: "👙", date: "2/4/2022"},
                {image: "", title: "👙", date: "2/11/2022"},
                {image: "", title: "👙", date: "2/18/2022"},
                {image: "", title: "👙", date: "2/25/2022"},
                {image: "", title: "🧸", date: "2/5/2022"},
                {image: "", title: "👨‍👩‍👦‍👦", date: "2/17/2022"},
                {image: "", title: "🎁", date: "1/22/2022"},
                {image: "", title: "🎳", date: "2/26/2022"},
                {image: "", title: "🌼", date: "3/20/2022"},
                {image: "", title: "🐇", date: "4/17/2022"},
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